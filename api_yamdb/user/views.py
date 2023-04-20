from django.contrib.auth.tokens import (default_token_generator,
                                        PasswordResetTokenGenerator)
from django.core.mail import send_mail
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import mixins
from rest_framework import status, generics
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken

from api_yamdb.settings import EMAIL_HOST_USER, TEMPLATES_DIR
from reviews.models import User
from user import serializers
from user.mixins import UpdateModelMixin
from user.permissions import (Admin)
from user.serializers import (UserSerializer, UserMeSerializer)


class CustomSignUp(generics.CreateAPIView, PasswordResetTokenGenerator):
    """Кастомная регистрация пользователя."""

    permission_classes = [AllowAny]
    serializer_class = serializers.SignUpSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data.get('username')
            email = serializer.validated_data['email']
            try:
                user, _ = User.objects.get_or_create(email=email,
                                                     username=username)
            except IntegrityError:
                raise ValidationError

            confirmation_code = default_token_generator.make_token(user)

            self.send_message(email, username, confirmation_code)

            return Response(
                serializer.data, status=status.HTTP_200_OK
            )
        else:
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

    def send_message(self, email, username, confirmation_code):
        context = {
            'username': username,
            'confirmation_code': confirmation_code
        }
        message = render_to_string(
            TEMPLATES_DIR/'email_templates/confirmation_mail.html', context)

        send_mail(
            'Код подтверждения',
            message,
            EMAIL_HOST_USER,
            [email],
            html_message=message
        )


class GetToken(generics.ListCreateAPIView):
    """Получение токена пользователем."""

    serializer_class = serializers.ConfirmationSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data.get('username')
            confirmation_code = serializer.validated_data.get(
                'confirmation_code')
            user = get_object_or_404(User, username=username)
            if default_token_generator.check_token(user, confirmation_code):
                token = AccessToken.for_user(user)
                return Response({'token': str(token)},
                                status=status.HTTP_200_OK)
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.data,
                            status=status.HTTP_400_BAD_REQUEST)


class UsersViewSet(mixins.CreateModelMixin, mixins.DestroyModelMixin,
                   mixins.ListModelMixin, UpdateModelMixin,
                   mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):
    """
    Получить список всех пользователей,
    добавить нового пользователя,
    получить пользователя по username,
    изменить данные пользователя по username,
    удалить пользователя по username,
    получить данные своей учетной записи по (англ.) me,
    изменить данные своей учетной записи по (англ.) me.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = "username"
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    search_fields = ('=username',)
    pagination_class = LimitOffsetPagination
    permission_classes = (Admin,)

    @action(methods=['get', 'patch'], detail=False, url_path='me',
            permission_classes=(IsAuthenticated,),
            serializer_class=UserMeSerializer)
    def me(self, request):
        user = get_object_or_404(User, username=request.user.username)
        if request.method == "GET":
            serializer = self.get_serializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        if request.method == "PATCH":
            serializer = self.get_serializer(user, data=request.data,
                                             partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
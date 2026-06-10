from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response

from auth_app.api.serializer import RegisterSerializer

# Create your views here.

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
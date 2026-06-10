from django.shortcuts import render

# Create your views here.

class RegisterView(APIView):
    def post(self,request):
        serializer = RegisterSerializer(data=request.data)
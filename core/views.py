from django.shortcuts import render


def home(request):
    """View para a página inicial"""
    return render(request, 'homepage.html')

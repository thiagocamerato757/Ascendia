from django.views.generic import TemplateView


class HomeView(TemplateView):
    """View para a página inicial"""
    template_name = 'homepage.html'

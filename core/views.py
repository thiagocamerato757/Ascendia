"""
Main project views.

This module contains generic views for main pages
of the system, such as homepage and static pages.
"""

from django.views.generic import TemplateView


class HomeView(TemplateView):
    """
    Homepage view.
    
    Renders Ascendia's homepage with Aurora Borealis animations
    and login/signup options for unauthenticated users.
    
    Attributes:
        template_name (str): Homepage HTML template
    """
    
    template_name = 'homepage.html'

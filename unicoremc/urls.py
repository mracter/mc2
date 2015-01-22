from django.conf.urls import patterns, url
from django.views.generic.base import TemplateView
from django.contrib.auth.decorators import login_required, permission_required
from unicoremc import views


urlpatterns = patterns(
    '',
    url(
        r'^$',
        login_required(
            TemplateView.as_view(template_name='unicoremc/home.html')),
        name='home'
    ),
    url(
        r'^login/$',
        TemplateView.as_view(template_name='unicoremc/login.html'),
        name='login'
    ),
    url(
        r'^new/$',
        'unicoremc.views.new_project_view',
        name='new_project'
    ),
    url(
        r'^googleanalytics/$',
        'unicoremc.views.manage_ga_view',
        name='manage_ga'
    ),
    url(
        r'^googleanalytics/new/$',
        'unicoremc.views.manage_ga_new',
        name='manage_ga_new'
    ),
    url(
        r'^new/create/$',
        'unicoremc.views.start_new_project',
        name='start_new_project'
    ),
    url(
        r'^progress/$',
        'unicoremc.views.projects_progress',
        name='projects_progress'
    ),
    url(
        r'^advanced/(?P<project_id>\d+)/$',
        permission_required('project.can_change')(
            login_required(views.ProjectEditView.as_view())),
        name='advanced'),
    url(
        r'^logout/$',
        'django.contrib.auth.views.logout_then_login',
        name='logout'
    ),
    url(
        r'^repos/$',
        'unicoremc.views.get_all_repos',
        name='get_all_repos'
    ),
)

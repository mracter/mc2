import json
import os
import shutil
import pytest
import responses

from django.conf import settings
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from unicoremc.constants import LANGUAGES
from unicoremc.models import Project, Localisation
from unicoremc.manager import DbManager
from unicore.content.models import (
    Category, Page, Localisation as EGLocalisation)
from unicoremc.tests.base import UnicoremcTestCase

from mock import patch

from pycountry import languages
from icu import Locale


@pytest.mark.django_db
class ViewsTestCase(UnicoremcTestCase):
    fixtures = ['test_users.json', 'test_social_auth.json']

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='test')

        self.mk_test_repos()

    @responses.activate
    def test_create_new_project(self):
        self.client.login(username='testuser2', password='test')

        self.mock_create_repo()
        self.mock_create_webhook()

        data = {
            'app_type': 'ffl',
            'base_repo': self.base_repo_sm.repo.git_dir,
            'country': 'ZA',
            'access_token': 'some-access-token',
            'user_id': 1,
            'team_id': 1
        }

        with patch.object(DbManager, 'call_subprocess') as mock_subprocess:
            mock_subprocess.return_value = None
            response = self.client.post(reverse('start_new_project'), data)

        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(json.loads(response.content), {
            'success': True
        })

        project = Project.objects.all()[0]
        self.assertEqual(project.state, 'done')

        workspace = self.mk_workspace(
            working_dir=settings.CMS_REPO_PATH,
            name='ffl-za',
            index_prefix='unicore_cms_ffl_za')

        self.assertEqual(workspace.S(Category).count(), 1)
        self.assertEqual(workspace.S(Page).count(), 1)
        self.assertEqual(workspace.S(EGLocalisation).count(), 1)

        cat = Category({
            'title': 'Some title',
            'slug': 'some-slug'
        })
        workspace.save(cat, 'Saving a Category')

        page = Page({
            'title': 'Some page title',
            'slug': 'some-page-slug'
        })
        workspace.save(page, 'Saving a Page')

        loc = EGLocalisation({
            'locale': 'spa_ES',
            'image': 'some-image-uuid',
            'image_host': 'http://some.site.com',
        })
        workspace.save(loc, 'Saving a Localisation')

        workspace.refresh_index()

        self.assertEqual(workspace.S(Category).count(), 2)
        self.assertEqual(workspace.S(Page).count(), 2)
        self.assertEqual(workspace.S(EGLocalisation).count(), 2)

        self.addCleanup(lambda: shutil.rmtree(
            os.path.join(settings.CMS_REPO_PATH, 'ffl-za')))
        self.addCleanup(lambda: shutil.rmtree(
            os.path.join(settings.FRONTEND_REPO_PATH, 'ffl-za')))

    @responses.activate
    def test_advanced_page(self):
        self.client.login(username='testuser2', password='test')

        self.mock_create_repo()
        self.mock_create_webhook()

        Localisation._for('eng_UK')
        Localisation._for('swa_TZ')

        data = {
            'app_type': 'ffl',
            'base_repo': self.base_repo_sm.repo.git_dir,
            'country': 'ZA',
            'access_token': 'some-access-token',
            'user_id': 1,
            'team_id': 1
        }

        with patch.object(DbManager, 'call_subprocess') as mock_subprocess:
            mock_subprocess.return_value = None
            self.client.post(reverse('start_new_project'), data)

        project = Project.objects.all()[0]

        frontend_settings_path = os.path.join(
            settings.FRONTEND_SETTINGS_OUTPUT_PATH,
            'ffl_za.ini')

        self.assertTrue(os.path.exists(frontend_settings_path))
        with open(frontend_settings_path, "r") as config_file:
            data = config_file.read()

        self.assertTrue("available_languages = []" in data)
        self.assertTrue('pyramid.default_locale_name = eng_GB' in data)
        self.assertFalse('ga.profile_id' in data)

        resp = self.client.get(reverse('advanced', args=[project.id]))

        self.assertContains(resp, 'English')
        self.assertContains(resp, 'Swahili')

        self.assertEqual(project.available_languages.count(), 0)
        self.assertIsNone(project.default_language)

        resp = self.client.post(
            reverse('advanced', args=[project.id]), {
                'available_languages': [1, 2],
                'default_language': [Localisation._for('swa_TZ').pk],
                'ga_profile_id': 'UA-some-profile-id'})
        project = Project.objects.get(pk=project.id)
        self.assertEqual(project.available_languages.count(), 2)
        self.assertEqual(project.default_language.get_code(), 'swa_TZ')

        frontend_settings_path = os.path.join(
            settings.FRONTEND_SETTINGS_OUTPUT_PATH,
            'ffl_za.ini')

        with open(frontend_settings_path, "r") as config_file:
            data = config_file.read()

        self.assertTrue(
            "[(u'eng_UK', u'English'), "
            "(u'swa_TZ', u'Swahili')]" in data)
        self.assertTrue('pyramid.default_locale_name = swa_TZ' in data)
        self.assertTrue('ga.profile_id = UA-some-profile-id' in data)

        self.addCleanup(lambda: shutil.rmtree(
            os.path.join(settings.CMS_REPO_PATH, 'ffl-za')))
        self.addCleanup(lambda: shutil.rmtree(
            os.path.join(settings.FRONTEND_REPO_PATH, 'ffl-za')))

    def test_view_only_on_homepage(self):
        resp = self.client.get(reverse('home'))
        self.assertNotContains(resp, 'Start new project')
        self.assertNotContains(resp, 'edit')

        self.client.login(username='testuser2', password='test')

        resp = self.client.get(reverse('home'))
        self.assertContains(resp, 'Start new project')
        self.assertContains(resp, 'edit')

    def test_staff_access_required(self):
        p = Project(
            app_type='ffl',
            base_repo_url='http://some-git-repo.com',
            country='ZA',
            owner=User.objects.get(pk=2))
        p.save()

        resp = self.client.get(reverse('new_project'))
        self.assertEqual(resp.status_code, 302)

        resp = self.client.get(reverse('start_new_project'))
        self.assertEqual(resp.status_code, 302)

        resp = self.client.get(reverse('advanced', args=[1]))
        self.assertEqual(resp.status_code, 302)

    @responses.activate
    def test_no_repos(self):
        self.client.login(username='testuser2', password='test')
        self.mock_list_repos()

        self.client.get(reverse('get_all_repos'))

    @patch('unicoremc.utils.create_ga_profile')
    @patch('unicoremc.utils.get_ga_accounts')
    def test_manage_ga(self, mock_get_ga_accounts, mock_create_ga_profile):
        mock_get_ga_accounts.return_value = [
            {'id': '1', 'name': 'Account 1'},
            {'id': '2', 'name': 'GEM Test Account'},
        ]
        mock_create_ga_profile.return_value = "UA-some-new-profile-id"

        p = Project.objects.create(
            app_type='ffl',
            base_repo_url='http://some-git-repo.com',
            country='ZA',
            owner=User.objects.get(pk=2),
            state='done')
        Project.objects.create(
            app_type='gem',
            base_repo_url='http://some-git-repo.com',
            country='ZA',
            owner=User.objects.get(pk=2))

        self.client.login(username='testuser2', password='test')
        resp = self.client.get(reverse('manage_ga'))
        self.assertContains(resp, 'Facts for Life')
        self.assertNotContains(resp, 'Girl Effect Mobile')
        self.assertContains(resp, 'Account 1')
        self.assertContains(resp, 'GEM Test Account')

        data = {
            'account_id': 'some-account-id',
            'project_id': p.id,
            'access_token': 'some-access-token',
        }
        resp = self.client.post(reverse('manage_ga_new'), data)
        self.assertEqual(resp['Content-Type'], 'application/json')
        self.assertEqual(json.loads(resp.content), {
            'ga_profile_id': 'UA-some-new-profile-id'
        })
        p = Project.objects.get(pk=p.id)
        self.assertEqual(p.ga_profile_id, 'UA-some-new-profile-id')
        self.assertEqual(p.ga_account_id, 'some-account-id')

        resp = self.client.get(reverse('manage_ga_new'), data)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.content, "You can only call this using a POST")

        resp = self.client.post(reverse('manage_ga_new'), data)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.content, "Project already has a profile")

    def test_all_language_codes(self):
        unsupported = {}
        for k, v in LANGUAGES.items():
            lang = languages.get(bibliographic=k)
            locale = Locale(lang.terminology)
            # an invalid code will have no ISO3Language code
            if not locale.getISO3Language():
                unsupported.update(
                    {lang.terminology: '%s(%s)' % (lang.name, k)})
        if unsupported:
            print 'Total unsupported: %s/%s' % (
                len(unsupported.items()), len(LANGUAGES.items()))
        self.assertEqual(unsupported, {})

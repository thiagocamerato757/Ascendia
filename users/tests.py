from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from .models import Profile
from .forms import SignUpForm, UserUpdateForm, ProfileUpdateForm
import json
import base64
import tempfile
import shutil


# Create a temporary directory for test media files
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Profile should be created automatically via signal
        self.profile = self.user.profile
    
    def test_profile_creation_signal(self):
        self.assertIsNotNone(self.profile)
        self.assertEqual(self.profile.user, self.user)
    
    def test_profile_str_representation(self):
        expected = f'{self.user.username} Profile'
        self.assertEqual(str(self.profile), expected)
    
    def test_profile_avatar_url_without_avatar(self):
        self.assertIsNone(self.profile.avatar_url)
    
    def test_profile_avatar_url_with_avatar(self):
        # Create a dummy image file
        image_content = b'GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
        image_file = SimpleUploadedFile(
            name='test_avatar.gif',
            content=image_content,
            content_type='image/gif'
        )
        self.profile.avatar = image_file
        self.profile.save()
        
        self.assertIsNotNone(self.profile.avatar_url)
        self.assertIn('avatars/', self.profile.avatar_url)
    
    def test_profile_whatsapp_link_without_number(self):
        self.assertIsNone(self.profile.whatsapp_link)
    
    def test_profile_whatsapp_link_with_number(self):
        self.profile.whatsapp = '+55 11 98765-4321'
        self.profile.save()
        
        expected_url = 'https://wa.me/5511987654321'
        self.assertEqual(self.profile.whatsapp_link, expected_url)
    
    def test_profile_whatsapp_link_removes_special_chars(self):
        self.profile.whatsapp = '+1 (555) 123-4567'
        self.profile.save()
        
        expected_url = 'https://wa.me/15551234567'
        self.assertEqual(self.profile.whatsapp_link, expected_url)
    
    def test_profile_ordering(self):
        user2 = User.objects.create_user(username='auser', password='pass123')
        user3 = User.objects.create_user(username='zuser', password='pass123')
        
        profiles = list(Profile.objects.all())
        usernames = [p.user.username for p in profiles]
        
        self.assertEqual(usernames, ['auser', 'testuser', 'zuser'])
    
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


class SignUpFormTests(TestCase):
    def test_signup_form_valid_data(self):
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complex_pass123',
            'password2': 'complex_pass123',
        }
        form = SignUpForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_signup_form_missing_email(self):
        form_data = {
            'username': 'newuser',
            'email': '',
            'password1': 'complex_pass123',
            'password2': 'complex_pass123',
        }
        form = SignUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_signup_form_invalid_email(self):
        form_data = {
            'username': 'newuser',
            'email': 'invalid-email',
            'password1': 'complex_pass123',
            'password2': 'complex_pass123',
        }
        form = SignUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_signup_form_password_mismatch(self):
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complex_pass123',
            'password2': 'different_pass456',
        }
        form = SignUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_signup_form_saves_user_with_email(self):
        form_data = {
            'username': 'emailuser',
            'email': 'emailuser@example.com',
            'password1': 'complex_pass123',
            'password2': 'complex_pass123',
        }
        form = SignUpForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertEqual(user.email, 'emailuser@example.com')
        self.assertEqual(user.username, 'emailuser')


class UserUpdateFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_update_form_valid_data(self):
        form_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        self.assertTrue(form.is_valid())
    
    def test_user_update_form_missing_email(self):
        form_data = {
            'username': 'updateduser',
            'email': '',
            'first_name': 'John',
            'last_name': 'Doe',
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class ProfileUpdateFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = self.user.profile
    
    def test_profile_update_form_valid_whatsapp(self):
        form_data = {
            'whatsapp': '+55 11 98765-4321',
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        self.assertTrue(form.is_valid())
    
    def test_profile_update_form_whatsapp_without_country_code(self):
        form_data = {
            'whatsapp': '11 98765-4321',
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('whatsapp', form.errors)
    
    def test_profile_update_form_whatsapp_too_short(self):
        form_data = {
            'whatsapp': '+55 123',
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('whatsapp', form.errors)
    
    def test_profile_update_form_empty_whatsapp(self):
        form_data = {
            'whatsapp': '',
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        self.assertTrue(form.is_valid())


class SignUpViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('signup')
    
    def test_signup_view_get(self):
        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/signup.html')
    
    def test_signup_view_post_valid_data(self):
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complex_pass123',
            'password2': 'complex_pass123',
        }
        response = self.client.post(self.signup_url, form_data)
        
        # Should redirect to home page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        
        self.assertTrue(User.objects.filter(username='newuser').exists())
        
        # User should be logged in automatically
        user = User.objects.get(username='newuser')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
    
    def test_signup_view_post_invalid_data(self):
        form_data = {
            'username': 'newuser',
            'email': 'invalid-email',
            'password1': 'pass123',
            'password2': 'different',
        }
        response = self.client.post(self.signup_url, form_data)
        
        # Should stay on signup page with errors
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'email', 
                           'Enter a valid email address.')
    
    def test_signup_view_redirects_authenticated_user(self):
        user = User.objects.create_user(
            username='existinguser',
            password='testpass123'
        )
        self.client.login(username='existinguser', password='testpass123')
        
        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_login_view_get(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
    
    def test_login_view_post_valid_credentials(self):
        form_data = {
            'username': 'testuser',
            'password': 'testpass123',
        }
        response = self.client.post(self.login_url, form_data)
        
        # Should redirect to home page
        self.assertEqual(response.status_code, 302)
        
        # User should be logged in
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
    
    def test_login_view_post_invalid_credentials(self):
        form_data = {
            'username': 'testuser',
            'password': 'wrongpassword',
        }
        response = self.client.post(self.login_url, form_data)
        
        # Should stay on login page with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password', 
                          status_code=200)
    
    def test_login_view_success_message(self):
        form_data = {
            'username': 'testuser',
            'password': 'testpass123',
        }
        response = self.client.post(self.login_url, form_data, follow=True)
        
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('Welcome back', str(messages[0]))


class ProfileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.profile_url = reverse('profile')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.profile = self.user.profile
    
    def test_profile_view_requires_login(self):
        self.client.logout()
        response = self.client.get(self.profile_url)
        
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_profile_view_get(self):
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/profile.html')
        self.assertIn('user_form', response.context)
        self.assertIn('profile_form', response.context)
    
    def test_profile_view_post_update_user_info(self):
        form_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'whatsapp': '+55 11 98765-4321',
        }
        response = self.client.post(self.profile_url, form_data)
        
        # Should redirect back to profile
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.profile_url)
        
        # User should be updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'updateduser')
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        
        # Profile should be updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.whatsapp, '+55 11 98765-4321')
    
    def test_profile_view_creates_profile_if_missing(self):
        Profile.objects.filter(user=self.user).delete()
        
        response = self.client.get(self.profile_url)
        
        # Profile should be recreated
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertEqual(response.status_code, 200)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AvatarUpdateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.avatar_url = reverse('update_avatar')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.profile = self.user.profile
    
    def test_avatar_update_requires_login(self):
        self.client.logout()
        response = self.client.post(self.avatar_url)
        
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
    
    def test_avatar_update_only_accepts_post(self):
        response = self.client.get(self.avatar_url)
        
        self.assertEqual(response.status_code, 405)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
    
    def test_avatar_update_delete_avatar(self):
        # First, add an avatar
        image_content = b'GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
        image_file = SimpleUploadedFile(
            name='test_avatar.gif',
            content=image_content,
            content_type='image/gif'
        )
        self.profile.avatar = image_file
        self.profile.save()
        
        response = self.client.post(self.avatar_url, {'delete_avatar': 'true'})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIsNone(data['avatar_url'])
        
        # Profile should have no avatar
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)
    
    def test_avatar_update_upload_cropped_image(self):
        # Create a small base64 encoded image
        image_data = b'GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
        base64_data = base64.b64encode(image_data).decode('utf-8')
        data_uri = f'data:image/gif;base64,{base64_data}'
        
        response = self.client.post(self.avatar_url, {'avatar_cropped': data_uri})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIsNotNone(data['avatar_url'])
        
        # Profile should have avatar
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.avatar)
        self.assertIn('avatars/', self.profile.avatar.name)
    
    def test_avatar_update_no_data_provided(self):
        response = self.client.post(self.avatar_url, {})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('No avatar data provided', data['error'])
    
    def test_avatar_update_replaces_old_avatar(self):
        # Upload first avatar
        image_data1 = b'GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
        base64_data1 = base64.b64encode(image_data1).decode('utf-8')
        data_uri1 = f'data:image/gif;base64,{base64_data1}'
        
        self.client.post(self.avatar_url, {'avatar_cropped': data_uri1})
        self.profile.refresh_from_db()
        first_avatar_name = self.profile.avatar.name
        
        # Upload second avatar
        image_data2 = b'GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
        base64_data2 = base64.b64encode(image_data2).decode('utf-8')
        data_uri2 = f'data:image/png;base64,{base64_data2}'
        
        response = self.client.post(self.avatar_url, {'avatar_cropped': data_uri2})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Profile should have new avatar
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.avatar.name, first_avatar_name)
    
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


class LogoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.logout_url = reverse('logout')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_logout_view(self):
        self.assertIn('_auth_user_id', self.client.session)
        
        response = self.client.post(self.logout_url)
        
        # Should redirect to home page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        
        # User should be logged out
        self.assertNotIn('_auth_user_id', self.client.session)


class HomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.home_url = reverse('home')
    
    def test_home_view_get(self):
        response = self.client.get(self.home_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'homepage.html')
    
    def test_home_view_accessible_without_login(self):
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
    
    def test_home_view_accessible_with_login(self):
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)


class CSRFProtectionTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username='csrftest',
            email='csrf@example.com',
            password='testpass123'
        )
        self.signup_url = reverse('signup')
        self.profile_url = reverse('profile')
        self.update_avatar_url = reverse('update_avatar')
        self.logout_url = reverse('logout')
    
    def test_signup_requires_csrf_token(self):
        response = self.client.post(self.signup_url, {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!'
        })
        # Should be rejected due to missing CSRF token
        self.assertEqual(response.status_code, 403)
    
    def test_signup_works_with_csrf_token(self):
        # Get CSRF token first
        response = self.client.get(self.signup_url)
        csrf_token = response.cookies.get('csrftoken').value
        
        response = self.client.post(self.signup_url, {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'csrfmiddlewaretoken': csrf_token
        })
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_profile_update_requires_csrf_token(self):
        self.client.force_login(self.user)
        
        response = self.client.post(self.profile_url, {
            'username': 'updateduser',
            'email': 'updated@example.com'
        })
        
        # Should be rejected due to missing CSRF token
        self.assertEqual(response.status_code, 403)
    
    def test_avatar_update_requires_csrf_token(self):
        self.client.force_login(self.user)
        
        response = self.client.post(self.update_avatar_url, {
            'avatar_cropped': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        })
        
        # Should be rejected due to missing CSRF token
        self.assertEqual(response.status_code, 403)
    
    def test_logout_requires_csrf_token(self):
        self.client.force_login(self.user)
        
        response = self.client.post(self.logout_url)
        
        # Should be rejected due to missing CSRF token
        self.assertEqual(response.status_code, 403)


class SQLInjectionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='sqltest',
            email='sql@example.com',
            password='testpass123'
        )
        self.signup_url = reverse('signup')
        self.login_url = reverse('login')
        self.profile_url = reverse('profile')
    
    def test_sql_injection_in_signup_username(self):
        malicious_username = "admin' OR '1'='1"
        
        response = self.client.post(self.signup_url, {
            'username': malicious_username,
            'email': 'malicious@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!'
        })
        
        # Should not create admin user or cause errors
        self.assertFalse(User.objects.filter(username='admin').exists())
        # The malicious username might be created as literal string
        if response.status_code == 302:  # If form was valid
            user = User.objects.filter(username=malicious_username).first()
            if user:
                # Verify it's stored as literal, not executed
                self.assertEqual(user.username, malicious_username)
    
    def test_sql_injection_in_login_username(self):
        malicious_username = "' OR '1'='1' --"
        
        response = self.client.post(self.login_url, {
            'username': malicious_username,
            'password': 'anypassword'
        })
        
        # Should not bypass authentication
        self.assertNotIn('_auth_user_id', self.client.session)
        # Should redirect to login (not authenticated)
        self.assertEqual(response.status_code, 200)  # Login form shown again
    
    def test_sql_injection_in_email_field(self):
        malicious_email = "test@example.com' OR '1'='1"
        
        response = self.client.post(self.signup_url, {
            'username': 'testuser123',
            'email': malicious_email,
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!'
        })
        
        # Should fail validation (invalid email format) or be stored as literal
        if response.status_code == 200:
            # Form rejected - check that form has errors
            self.assertIn('form', response.context)
            form = response.context['form']
            self.assertTrue(form.errors.get('email') or not form.is_valid())
    
    def test_sql_injection_in_profile_fields(self):
        self.client.login(username='sqltest', password='testpass123')
        
        malicious_data = {
            'username': "admin' OR '1'='1",
            'email': 'test@example.com',
            'first_name': "'; DROP TABLE users; --",
            'last_name': "' OR '1'='1' --",
            'whatsapp': "+55'; DELETE FROM auth_user; --"
        }
        
        response = self.client.post(self.profile_url, malicious_data)
        
        # Verify database is intact
        self.assertTrue(User.objects.filter(username='sqltest').exists())
        
        # If update succeeded, verify data is stored as literal strings
        self.user.refresh_from_db()
        if self.user.first_name:
            # Data should be stored as-is, not executed
            self.assertIsInstance(self.user.first_name, str)


class XSSProtectionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='xsstest',
            email='xss@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        self.signup_url = reverse('signup')
        self.profile_url = reverse('profile')
    
    def test_xss_in_signup_username(self):
        xss_username = '<script>alert("XSS")</script>'
        
        response = self.client.post(self.signup_url, {
            'username': xss_username,
            'email': 'xsstest@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!'
        })
        
        # Username might be created (if valid according to Django's rules)
        # But the script should not be executable in rendered HTML
        user = User.objects.filter(username__contains='script').first()
        if user:
            # Verify it's stored as literal text
            self.assertIn('<script>', user.username)
    
    def test_xss_in_profile_first_name(self):
        self.client.login(username='xsstest', password='testpass123')
        
        xss_payload = '<img src=x onerror=alert("XSS")>'
        
        response = self.client.post(self.profile_url, {
            'username': 'xsstest',
            'email': 'xss@example.com',
            'first_name': xss_payload,
            'last_name': 'Test'
        })
        
        # Reload user and get profile page
        self.user.refresh_from_db()
        response = self.client.get(self.profile_url)
        content = response.content.decode('utf-8')
        
        # Verify that script tags are escaped in HTML output
        # Django auto-escapes by default, so < should become &lt;
        if xss_payload in content:
            # Should be escaped
            self.fail("XSS payload not escaped in HTML output")
        
        # The escaped version should be present or the tag should not be executable
        # Check that either it's escaped or not present as-is
        self.assertTrue('&lt;' in content or '<img src=x onerror=alert("XSS")>' not in content)
    
    def test_xss_in_profile_last_name(self):
        self.client.login(username='xsstest', password='testpass123')
        
        xss_payload = '"><script>alert(document.cookie)</script>'
        
        response = self.client.post(self.profile_url, {
            'username': 'xsstest',
            'email': 'xss@example.com',
            'first_name': 'John',
            'last_name': xss_payload
        })
        
        response = self.client.get(self.profile_url)
        content = response.content.decode('utf-8')
        
        # Script should be escaped
        self.assertNotIn('<script>alert(document.cookie)</script>', content)
    
    def test_xss_in_whatsapp_field(self):
        self.client.login(username='xsstest', password='testpass123')
        
        xss_payload = '+55<script>alert("XSS")</script>11999999999'
        
        response = self.client.post(self.profile_url, {
            'username': 'xsstest',
            'email': 'xss@example.com',
            'whatsapp': xss_payload
        })
        
        # WhatsApp field should validate and clean the input
        # or store it safely
        profile = self.user.profile
        profile.refresh_from_db()
        
        # Get profile page to check rendering
        response = self.client.get(self.profile_url)
        content = response.content.decode('utf-8')
        
        # Ensure script is not executable
        self.assertNotIn('<script>alert("XSS")</script>', content)
    
    def test_xss_in_email_field(self):
        xss_email = 'test@example.com<script>alert("XSS")</script>'
        
        response = self.client.post(self.signup_url, {
            'username': 'xssemailtest',
            'email': xss_email,
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!'
        })
        
        # Should fail email validation
        if response.status_code == 200:
            # Form should have errors
            self.assertIn('form', response.context)
            form = response.context['form']
            self.assertTrue(form.errors.get('email') or not form.is_valid())
        
        # Verify user wasn't created with malicious email
        self.assertFalse(
            User.objects.filter(email__contains='<script>').exists()
        )


class RememberMeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='remembertest',
            email='remember@example.com',
            password='testpass123'
        )
        self.login_url = reverse('login')
    
    def test_login_without_remember_me(self):
        response = self.client.post(self.login_url, {
            'username': 'remembertest',
            'password': 'testpass123'
        }, follow=True)
        
        # Should be logged in
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        
        # Session should expire on browser close
        # get_expire_at_browser_close() returns True when expiry is 0
        self.assertTrue(self.client.session.get_expire_at_browser_close())
    
    def test_login_with_remember_me(self):
        response = self.client.post(self.login_url, {
            'username': 'remembertest',
            'password': 'testpass123',
            'remember_me': 'on'
        }, follow=True)
        
        # Should be logged in
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        
        # Session should have extended expiry (2 weeks = 1209600 seconds)
        session_age = self.client.session.get_expiry_age()
        self.assertGreater(session_age, 0)
        # Should be approximately 2 weeks (allow some variance)
        self.assertGreater(session_age, 1200000)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='resettest',
            email='reset@example.com',
            password='oldpassword123'
        )
        self.password_reset_url = reverse('password_reset')
        self.password_reset_done_url = reverse('password_reset_done')
    
    def test_password_reset_page_accessible(self):
        response = self.client.get(self.password_reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset.html')
    
    def test_password_reset_form_submission(self):
        response = self.client.post(self.password_reset_url, {
            'email': 'reset@example.com'
        })
        
        # Should redirect to done page
        self.assertRedirects(response, self.password_reset_done_url)
    
    def test_password_reset_email_sent(self):
        from django.core import mail
        
        response = self.client.post(self.password_reset_url, {
            'email': 'reset@example.com'
        })
        
        # Should send one email
        self.assertEqual(len(mail.outbox), 1)
        
        # Verify email content
        email = mail.outbox[0]
        self.assertIn('reset@example.com', email.to)
        self.assertIn('reset', email.subject.lower())
    
    def test_password_reset_with_nonexistent_email(self):
        response = self.client.post(self.password_reset_url, {
            'email': 'nonexistent@example.com'
        })
        
        # Should still redirect to done page (security feature)
        self.assertRedirects(response, self.password_reset_done_url)
    
    def test_password_reset_confirm_valid_token(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        
        # Access reset confirm page
        reset_url = reverse('password_reset_confirm', kwargs={
            'uidb64': uid,
            'token': token
        })
        
        response = self.client.get(reset_url)
        # Should redirect to set password form
        self.assertEqual(response.status_code, 302)
    
    def test_password_reset_complete_flow(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        
        # Get reset URL with token
        reset_url = reverse('password_reset_confirm', kwargs={
            'uidb64': uid,
            'token': token
        })
        
        # Follow redirect to get session key
        response = self.client.get(reset_url, follow=True)
        
        response = self.client.post(response.request['PATH_INFO'], {
            'new_password1': 'newpassword123',
            'new_password2': 'newpassword123'
        })
        
        self.user.refresh_from_db()
        
        # Should be able to login with new password
        login_success = self.client.login(
            username='resettest',
            password='newpassword123'
        )
        self.assertTrue(login_success)
        
        # Old password should not work
        self.client.logout()
        old_login = self.client.login(
            username='resettest',
            password='oldpassword123'
        )
        self.assertFalse(old_login)
    
    def test_password_reset_done_page(self):
        response = self.client.get(self.password_reset_done_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset_done.html')
    
    def test_password_reset_complete_page(self):
        complete_url = reverse('password_reset_complete')
        response = self.client.get(complete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset_complete.html')

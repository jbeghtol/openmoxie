from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.views import generic
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect
import qrcode
from PIL import Image
from io import BytesIO

from .models import SinglePromptChat, MoxieDevice, MoxieSchedule, HiveConfiguration
from .mqtt.moxie_server import get_instance
import uuid
import logging

logger = logging.getLogger(__name__)

def root_view(request):
    cfg = HiveConfiguration.objects.filter(name='default')
    if cfg:
        return HttpResponseRedirect(reverse("hive:dashboard"))
    else:
        return HttpResponseRedirect(reverse("hive:setup"))

class SetupView(generic.TemplateView):
    template_name = "hive/setup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()
        context['needs_admin'] = not User.objects.filter(is_superuser=True).exists()
        return context

@require_http_methods(["POST"])
def hive_configure(request):
    cfg, created = HiveConfiguration.objects.get_or_create(name='default')
    cfg.openai_api_key =  request.POST['apikey']
    cfg.external_host = request.POST['hostname']
    cfg.allow_unverified_bots = request.POST.get('allowall') == "on"
    cfg.save()

    # Create Admin User if data exists and we dont have one
    User = get_user_model()
    if not User.objects.filter(is_superuser=True).exists():
        admin = request.POST.get("admin")
        adminPassword = request.POST.get("adminPassword")
        if admin and adminPassword:
            User.objects.create_superuser(admin, None, adminPassword)
            logger.info(f"Created superuser '{admin}'")
        else:
            logger.warn(f"Couldn't create missing superuser")

    logger.info("Updated default Hive Configuration")
    # reload any cached db objects
    get_instance().update_from_database()
    return HttpResponseRedirect(reverse("hive:dashboard"))

class DashboardView(generic.TemplateView):
    template_name = "hive/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_devices'] = MoxieDevice.objects.all()
        context['conversations'] = SinglePromptChat.objects.all()
        context['schedules'] = MoxieSchedule.objects.all()
        context['live'] = get_instance().robot_data().connected_list()
        return context
    
class InteractionView(generic.DetailView):
    template_name = "hive/interact.html"
    model = SinglePromptChat

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = uuid.uuid4().hex
        return context

@require_http_methods(["POST"])
@csrf_exempt
def interact_update(request):
    speech = request.POST['speech']
    token = request.POST['token']
    module_id = request.POST['module_id']
    content_id = request.POST['content_id']
    session = get_instance().get_web_session_for_module(token, module_id, content_id)
    if not speech:
        line,overflow = session.get_prompt(),False
    else:
        line,overflow = session.next_response(speech)
    return JsonResponse({'message': line, 'overflow': overflow})

def reload_database(request):
    get_instance().update_from_database()
    return HttpResponseRedirect(reverse("hive:dashboard"))

def endpoint_qr(request):
    img = qrcode.make(get_instance().get_endpoint_qr_data())
    buffer = BytesIO()
    img.save(buffer, 'PNG')
    buffer.seek(0)
    return HttpResponse(buffer, content_type='image/png')

class MoxieView(generic.DetailView):
    template_name = "hive/moxie.html"
    model = MoxieDevice
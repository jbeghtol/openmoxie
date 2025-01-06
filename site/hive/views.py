from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.views import generic
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect
from django.conf import settings
import qrcode
from PIL import Image
from io import BytesIO

from .models import SinglePromptChat, MoxieDevice, MoxieSchedule, HiveConfiguration
from .mqtt.moxie_server import get_instance
from .mqtt.robot_data import DEFAULT_ROBOT_CONFIG, DEFAULT_ROBOT_SETTINGS
import json
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
        curr_cfg = HiveConfiguration.objects.filter(name='default').first()
        if curr_cfg:
            context['object'] = curr_cfg
        return context

@require_http_methods(["POST"])
def hive_configure(request):
    cfg, created = HiveConfiguration.objects.get_or_create(name='default')
    openai = request.POST['apikey']
    if openai:
        cfg.openai_api_key = openai
    google = request.POST['googleapikey']
    if google:
        cfg.google_api_key = google
    cfg.external_host = request.POST['hostname']
    cfg.allow_unverified_bots = request.POST.get('allowall') == "on"
    # Bootstrap any default data if not present
    if not cfg.common_config:
        cfg.common_config = DEFAULT_ROBOT_CONFIG
    if not cfg.common_settings:
        cfg.common_settings = DEFAULT_ROBOT_SETTINGS
    cfg.save()

    # Create Admin User if data exists and we dont have one
    User = get_user_model()
    if not User.objects.filter(is_superuser=True).exists():
        admin = request.POST.get("adminUser")
        adminPassword = request.POST.get("adminPassword")
        if admin and adminPassword:
            User.objects.create_superuser(admin, None, adminPassword)
            logger.info(f"Created superuser '{admin}'")
        else:
            logger.warning(f"Couldn't create missing superuser")

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

class WifiQREditView(generic.TemplateView):
    template_name = "hive/wifi.html"

@require_http_methods(["POST"])
def wifi_qr(request):
    ssid = request.POST['ssid']
    password = request.POST['password']
    band_id = request.POST['frequency']
    hidden = 'hidden' in request.POST
    img = qrcode.make(get_instance().get_wifi_qr_data(ssid, password, band_id, hidden))
    buffer = BytesIO()
    img.save(buffer, 'PNG')
    buffer.seek(0)
    return HttpResponse(buffer, content_type='image/png')

class MoxieView(generic.DetailView):
    template_name = "hive/moxie.html"
    model = MoxieDevice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_config'] = get_instance().robot_data().get_config_for_device(self.object)
        context['schedules'] = MoxieSchedule.objects.all()
        return context
    
@require_http_methods(["POST"])
def moxie_edit(request, pk):
    try:
        device = MoxieDevice.objects.get(pk=pk)
        # changes to base model
        device.name = request.POST["moxie_name"]
        device.schedule = MoxieSchedule.objects.get(pk=request.POST["schedule"])
        # changes to json field inside config
        if device.robot_config == None:
           # robot_config optional, create a new one to hold these
           device.robot_config = {}
        device.robot_config["screen_brightness"] = float(request.POST["screen_brightness"])
        device.robot_config["audio_volume"] = float(request.POST["audio_volume"])
        if "child_pii" in device.robot_config:
            device.robot_config["child_pii"]["nickname"] = request.POST["nickname"]
        else:
            device.robot_config["child_pii"] = { "nickname": request.POST["nickname"] }
        device.save()
        get_instance().handle_config_updated(device)
    except MoxieDevice.DoesNotExist as e:
        logger.warning("Moxie update for unfound pk {pk}")
    return HttpResponseRedirect(reverse("hive:dashboard"))
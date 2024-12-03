from django.shortcuts import render
from django.views import generic
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect

def dashboard(request):
    return HttpResponse("OpenMoxie Dashboard")
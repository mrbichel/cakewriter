# -*- coding: utf-8 -*-

from django.conf.urls.defaults import *
from voting.views import vote_on_object
from django.contrib.comments.models import Comment
from book import views
from djangoratings.views import AddRatingFromModel


urlpatterns = patterns('',
    url(r'^chapter/(?P<chapter_id>\d+)/$', views.chapter, name='chapter'),
    
    url(r'^chapter/(?P<chapter_id>\d+)/widget$', views.rating_widget, name='rating_widget'),
    
    url(r'^comment/(?P<object_id>\d+)/vote/(?P<direction>up|down|clear)/?$', vote_on_object, {
        'model': Comment,
        'template_object_name': 'comment',
        'allow_xmlhttprequest': True,
    }, name='vote-comment'),

    url(r'^chapter/(?P<chapter_id>\d+)/rate/$', views.rate_chapter, name='rate-chapter'),
    url(r'^chapter/(?P<chapter_id>\d+)/rate/(?P<score>\d+)/$', views.rate_chapter, name='rate-chapter'),
    
    
    (r'^api/getchapters/$', views.api_get_chapters),
    (r'^api/getchapter/(?P<chapter_id>\d+)/$', views.api_get_chapter),
    (r'^api/getcommentsforchapter/(?P<chapter_id>\d+)/$', views.api_get_comments_for_chapter),
)



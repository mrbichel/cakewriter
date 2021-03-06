# -*- coding: utf-8 -*-
import types
from django.core.urlresolvers import get_callable
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseServerError, HttpResponseForbidden, HttpResponseNotAllowed
from django.utils import simplejson
from django.shortcuts import get_object_or_404, render_to_response 
from django.template import RequestContext, Context, loader
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.conf import settings
from pages.models import Editpage
from django.contrib.comments.models import Comment
from book.models import Chapter
from usermessage.models import UserMessage

from models import *
from settings import *

def view(request, wiki_url):
    if request.GET and not request.user.is_anonymous():
        if 'usermessage' in request.GET:
            usermessage_id = int(request.GET['usermessage'])
            try:
                usermessage = UserMessage.objects.get(pk=usermessage_id, user=request.user)
                usermessage.delete()
            except:
                error = "Notification could not be deleted"
    chapters = Chapter.objects.filter(visible=True).extra(select={'r': '((100/%s*rating_score/(rating_votes+%s))+100)/2' % (Chapter.rating.range, Chapter.rating.weight)}).order_by('-r')
    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return err
        
    perm_err = check_permissions(request, article, check_read=True)
    if perm_err:
        return perm_err
    c = RequestContext(request, {'wiki_article': article,
                                 'wiki_write': article.can_write_l(request.user),
                                 'wiki_attachments_write': article.can_attach(request.user),
                                 'chapters': chapters,
                                 } ) 
    return render_to_response('simplewiki_view.html', c)

def discussion(request, wiki_url):
    if request.GET and not request.user.is_anonymous():
        if 'usermessage' in request.GET:
            usermessage_id = int(request.GET['usermessage'])
            try:
                usermessage = UserMessage.objects.get(pk=usermessage_id, user=request.user)
                usermessage.delete()
            except:
                error = "Notification could not be deleted"
    chapters = Chapter.objects.filter(visible=True).extra(select={'r': '((100/%s*rating_score/(rating_votes+%s))+100)/2' % (Chapter.rating.range, Chapter.rating.weight)}).order_by('-r')
    chapter = get_object_or_404(Article, slug=wiki_url)
    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return err

    # Check write permissions
    perm_err = check_permissions(request, article, check_write=True, check_locked=True)
    if perm_err:
        return perm_err
    c = RequestContext(request,{'chapters': chapters,'chapter': chapter,'wiki_article': article}) 
    return render_to_response('simplewiki_comments.html', c)

def root_redirect(request):
    editpage = Editpage.objects.all()
    chapters = Chapter.objects.filter(visible=True).extra(select={'r': '((100/%s*rating_score/(rating_votes+%s))+100)/2' % (Chapter.rating.range, Chapter.rating.weight)}).order_by('-r')
    try:
        root = Article.get_root()
    except:
        err = not_found(request, 'mainpage')
        return err
    
    return render_to_response(
        'simplewiki_root.html', {'chapters': chapters, 'editpage': editpage},
        context_instance = RequestContext(request)
    )

def create(request, wiki_url):
    
    url_path = get_url_path(wiki_url)

    if url_path != [] and url_path[0].startswith('_'):
            c = RequestContext(request, {'wiki_err_keyword': True,
                                         'wiki_url': '/'.join(url_path) })
            return render_to_response('simplewiki_error.html', c)        

    # Lookup path
    try:
        # Ensure that the path exists...
        root = Article.get_root()
        # Remove root slug if present in path
        if url_path and root.slug == url_path[0]:
            url_path = url_path[1:]
        
        path = Article.get_url_reverse(url_path[:-1], root)
        if not path:
            c = RequestContext(request, {'wiki_err_noparent': True,
                                         'wiki_url_parent': '/'.join(url_path[:-1]) })
            return render_to_response('simplewiki_error.html', c)
        
        perm_err = check_permissions(request, path[-1], check_locked=False, check_write=True)
        if perm_err:
            return perm_err
        # Ensure doesn't already exist
        article = Article.get_url_reverse(url_path, root)
        if article:
            return HttpResponseRedirect(reverse('wiki_view', args=(article[-1].get_url(),)))
    
        # TODO: Somehow this doesnt work... 
        #except ShouldHaveExactlyOneRootSlug, (e):
    except:
        if Article.objects.filter(parent=None).count() > 0:
            return HttpResponseRedirect(reverse('wiki_view', args=('',)))
        # Root not found...
        path = []
        url_path = [""]

    if request.method == 'POST':
        f = CreateArticleForm(request.POST)
        if f.is_valid():
            article = Article()
            article.slug = url_path[-1]
            if not request.user.is_anonymous():
                article.created_by = request.user
            article.title = f.cleaned_data.get('title')
            if path != []:
                article.parent = path[-1]
            a = article.save()
            new_revision = f.save(commit=False)
            if not request.user.is_anonymous():
                new_revision.revision_user = request.user
            new_revision.article = article
            new_revision.save()
            import django.db as db
            return HttpResponseRedirect(reverse('wiki_view', args=(article.get_url(),)))
    else:
        f = CreateArticleForm(initial={'title':request.GET.get('wiki_article_name', url_path[-1]),
                                       'contents':_('Headline\n===\n\n')})
        
    c = RequestContext(request, {'wiki_form': f,
                                 'wiki_write': True,
                                 })

    return render_to_response('simplewiki_create.html', c)

def edit(request, wiki_url):
    chapters = Chapter.objects.filter(visible=True).extra(select={'r': '((100/%s*rating_score/(rating_votes+%s))+100)/2' % (Chapter.rating.range, Chapter.rating.weight)}).order_by('-r')
    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return err

    # Check write permissions
    perm_err = check_permissions(request, article, check_write=True, check_locked=True)
    if perm_err:
        return perm_err

    if WIKI_ALLOW_TITLE_EDIT:
        EditForm = RevisionFormWithTitle
    else:
        EditForm = RevisionForm
    
    if request.method == 'POST':
        f = EditForm(request.POST)
        if f.is_valid():
            new_revision = f.save(commit=False)
            new_revision.article = article
            # Check that something has actually been changed...
            if not new_revision.get_diff():
                return (None, HttpResponseRedirect(reverse('wiki_view', args=(article.get_url(),))))
            if not request.user.is_anonymous():
                new_revision.revision_user = request.user
            new_revision.save()
            if WIKI_ALLOW_TITLE_EDIT:
                new_revision.article.title = f.cleaned_data['title']
                new_revision.article.save()
            return HttpResponseRedirect(reverse('wiki_view', args=(article.get_url(),)))
    else:
        f = EditForm({'contents': article.current_revision.contents, 'title': article.title})
    c = RequestContext(request, {'wiki_form': f,
                                 'wiki_write': True,
                                 'wiki_article': article,
                                 'wiki_attachments_write': article.can_attach(request.user),
                                 'chapters': chapters,
                                 })

    return render_to_response('simplewiki_edit.html', c)

def history(request, wiki_url, page=1):
    chapters = Chapter.objects.filter(visible=True).extra(select={'r': '((100/%s*rating_score/(rating_votes+%s))+100)/2' % (Chapter.rating.range, Chapter.rating.weight)}).order_by('-r')
    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return err

    perm_err = check_permissions(request, article, check_read=True)
    if perm_err:
        return perm_err

    page_size = 10
    
    try:
        p = int(page)
    except ValueError:
        p = 1
   
    history = Revision.objects.filter(article__exact = article).order_by('-counter')
    
    if request.method == 'POST':
        if request.POST.__contains__('revision'):
            perm_err = check_permissions(request, article, check_write=True, check_locked=True)
            if perm_err:
                return perm_err
            try:
                r = int(request.POST['revision'])
                article.current_revision = Revision.objects.get(id=r)
                article.save()
            except:
                pass
            finally:
                return HttpResponseRedirect(reverse('wiki_view', args=(article.get_url(),)))
    
    page_count = (history.count()+(page_size-1)) / page_size
    if p > page_count:
        p = 1
    beginItem = (p-1) * page_size
    
    next_page = p + 1 if page_count > p else None
    prev_page = p - 1 if p > 1 else None
    
    c = RequestContext(request, {'wiki_page': p,
                                 'wiki_next_page': next_page,
                                 'wiki_prev_page': prev_page,
                                 'wiki_write': article.can_write_l(request.user),
                                 'wiki_attachments_write': article.can_attach(request.user),
                                 'wiki_article': article,
                                 'wiki_history': history[beginItem:beginItem+page_size],
                                 'chapters': chapters,})

    return render_to_response('simplewiki_history.html', c)

def search_articles(request, wiki_url):
    # blampe: We should check for the presence of other popular django search
    # apps and use those if possible. Only fall back on this as a last resort.
    # Adding some context to results (eg where matches were) would also be nice.
    
    # todo: maybe do some perm checking here
    
    if request.method == 'POST':
        querystring = request.POST['value'].strip()
        if querystring:
            results = Article.objects.all()
            for queryword in querystring.split():
                # Basic negation is as fancy as we get right now
                if queryword[0] == '-' and len(queryword) > 1:
                    results._search = lambda x: results.exclude(x)
                    queryword = queryword[1:]
                else:
                    results._search = lambda x: results.filter(x)
                    
                results = results._search(Q(current_revision__contents__icontains = queryword) | \
                                          Q(title = queryword))
        else:
            # Need to throttle results by splitting them into pages...
            results = Article.objects.all()

        if results.count() == 1:
            return HttpResponseRedirect(reverse('wiki_view', args=(results[0].get_url(),)))
        else:        
            c = RequestContext(request, {'wiki_search_results': results,
                                         'wiki_search_query': querystring})
            return render_to_response('simplewiki_searchresults.html', c)
    
    return view(request, wiki_url)

def search_add_related(request, wiki_url):

    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return err

    perm_err = check_permissions(request, article, check_read=True)
    if perm_err:
        return perm_err

    search_string = request.GET.get('query', None)
    self_pk = request.GET.get('self', None)
    if search_string:
        results = []
        related = Article.objects.filter(title__istartswith = search_string)
        others = article.related.all()
        if self_pk:
            related = related.exclude(pk=self_pk)
        if others:
            related = related.exclude(related__in = others)
        related = related.order_by('title')[:10]
        for item in related:
            results.append({'id': str(item.id),
                            'value': item.title,
                            'info': item.get_url()})
    else:
        results = []
    
    json = simplejson.dumps({'results': results})
    return HttpResponse(json, mimetype='application/json')

def add_related(request, wiki_url):

    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return err
    
    perm_err = check_permissions(request, article, check_write=True, check_locked=True)
    if perm_err:
        return perm_err
    
    try:
        related_id = request.POST['id']
        rel = Article.objects.get(id=related_id)
        has_already = article.related.filter(id=related_id).count()
        if has_already == 0 and not rel == article:
            article.related.add(rel)
            article.save()
    except:
        pass
    finally:
        return HttpResponseRedirect(reverse('wiki_view', args=(article.get_url(),)))

def remove_related(request, wiki_url, related_id):

    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return err

    perm_err = check_permissions(request, article, check_write=True, check_locked=True)
    if perm_err:
        return perm_err

    try:
        rel_id = int(related_id)
        rel = Article.objects.get(id=rel_id)
        article.related.remove(rel)
        article.save()
    except:
        pass
    finally:
        return HttpResponseRedirect(reverse('wiki_view', args=(article.get_url(),)))

def random_article(request, wiki_url):
    from random import randint
    num_arts = Article.objects.count()
    article = Article.objects.all()[randint(0, num_arts-1)]
    return HttpResponseRedirect(reverse('wiki_view', args=(article.get_url(),)))

def encode_err(request, url):
    chapters = Article.objects.all()
    return render_to_response('simplewiki_error.html',
                              RequestContext(request, {'wiki_err_encode': True, 'chapters': chapters,}))
    
def not_found(request, wiki_url):
    """Generate a NOT FOUND message for some URL"""
    chapters = Chapter.objects.filter(visible=True).extra(select={'r': '((100/%s*rating_score/(rating_votes+%s))+100)/2' % (Chapter.rating.range, Chapter.rating.weight)}).order_by('-r')
    return render_to_response('simplewiki_error.html',
                              RequestContext(request, {'wiki_err_notfound': True,
                                                       'wiki_url': wiki_url,
                                                       'chapters': chapters,
                                                       }))

def get_url_path(url):
    """Return a list of all actual elements of a url, safely ignoring
    double-slashes (//) """
    return filter(lambda x: x!='', url.split('/'))

def fetch_from_url(request, url):
    """Analyze URL, returning the article and the articles in its path
    If something goes wrong, return an error HTTP response"""

    err = None
    article = None
    path = None
    
    url_path = get_url_path(url)

    try:
        root = Article.get_root()
    except:
        err = not_found(request, '')
        return (article, path, err)

    if url_path and root.slug == url_path[0]:
        url_path = url_path[1:]

    path = Article.get_url_reverse(url_path, root)
    if not path:
        err = not_found(request, '/' + '/'.join(url_path))
    else:
        article = path[-1]
    return (article, path, err)


def check_permissions(request, article, check_read=False, check_write=False, check_locked=False):
    read_err = check_read and not article.can_read(request.user)
    write_err = check_write and not article.can_write(request.user)
    locked_err = check_locked and article.locked

    if read_err or write_err or locked_err:
        c = RequestContext(request, {'wiki_article': article,
                                     'wiki_err_noread': read_err,
                                     'wiki_err_nowrite': write_err,
                                     'wiki_err_locked': locked_err,})
        # TODO: Make this a little less jarring by just displaying an error
        #       on the current page? (no such redirect happens for an anon upload yet)
        # benjaoming: I think this is the nicest way of displaying an error, but
        # these errors shouldn't occur, but rather be prevented on the other pages.
        return render_to_response('simplewiki_error.html', c)
    else:
        return None


####################
# LOGIN PROTECTION #
####################

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import available_attrs
import urlparse
from simplewiki.views import fetch_from_url
from functools import wraps

def is_author(user, request, wiki_url):
    (article, path, err) = fetch_from_url(request, wiki_url)
    if err:
        return False
    if article.created_by == user and user.is_authenticated and user.is_active:
        return True
    elif user.groups.filter(name='Editors') and user.is_authenticated and user.is_active:
        return True
    return False

def author_required(function, redirect_field_name=REDIRECT_FIELD_NAME, login_url=None):

    def _wrapped_view(request, wiki_url, *args, **kwargs):
        actual_decorator = user_passes_test(
            lambda user: is_author(user,request, wiki_url),
            login_url=login_url,
            redirect_field_name=redirect_field_name
        )(function)(request, wiki_url, *args, **kwargs)
        return actual_decorator
    return _wrapped_view


if WIKI_REQUIRE_LOGIN_VIEW:
    view            = author_required(view)
    history         = author_required(history)
    discussion      = author_required(discussion)

if WIKI_REQUIRE_LOGIN_EDIT:
    create          = author_required(create)
    edit            = author_required(edit)
    add_related     = author_required(add_related)
    remove_related  = author_required(remove_related)

if WIKI_CONTEXT_PREPROCESSORS:
    settings.TEMPLATE_CONTEXT_PROCESSORS = settings.TEMPLATE_CONTEXT_PROCESSORS + WIKI_CONTEXT_PREPROCESSORS

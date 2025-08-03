import asyncio
from functools import wraps
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import resolve_url, render
from django.http import HttpResponseRedirect, QueryDict


def redirect_to_hpc_login(next, hpc_login_url=None, redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Redirect the user to the HPC login page, passing the given 'next' page.
    """
    resolved_url = resolve_url(hpc_login_url or settings.HPC_LOGIN_URL)

    hpc_login_url_parts = list(urlparse(resolved_url))
    if redirect_field_name:
        querystring = QueryDict(hpc_login_url_parts[4], mutable=True)
        querystring[redirect_field_name] = next
        hpc_login_url_parts[4] = querystring.urlencode(safe="/")

    return HttpResponseRedirect(urlunparse(hpc_login_url_parts))


def hpc_user_passes_test(
    test_func, hpc_login_url=None, redirect_field_name=REDIRECT_FIELD_NAME
):
    """
    Decorator for views that checks that the HPC user passes the given test,
    redirecting to the log-in page if necessary. The test should be a callable
    that takes the user object and returns True if the user passes.
    """

    def decorator(view_func):
        def _redirect_to_hpc_login(request):
            path = request.build_absolute_uri()
            resolved_hpc_login_url = resolve_url(hpc_login_url or settings.HPC_LOGIN_URL)
            # If the hpc_login url is the same scheme and net location then just
            # use the path as the "next" url.
            hpc_login_scheme, hpc_login_netloc = urlparse(resolved_hpc_login_url)[:2]
            current_scheme, current_netloc = urlparse(path)[:2]
            if (not hpc_login_scheme or hpc_login_scheme == current_scheme) and (
                not hpc_login_netloc or hpc_login_netloc == current_netloc
            ):
                path = request.get_full_path()

            return redirect_to_hpc_login(path, resolved_hpc_login_url, redirect_field_name)

        if asyncio.iscoroutinefunction(view_func):

            async def _view_wrapper(request, *args, **kwargs):
                auser = await request.auser()
                if asyncio.iscoroutinefunction(test_func):
                    test_pass = await test_func(auser)
                else:
                    test_pass = await sync_to_async(test_func)(auser)

                if test_pass:
                    return await view_func(request, *args, **kwargs)
                return _redirect_to_hpc_login(request)

        else:

            def _view_wrapper(request, *args, **kwargs):
                if asyncio.iscoroutinefunction(test_func):
                    test_pass = async_to_sync(test_func)(request.user)
                else:
                    test_pass = test_func(request.user)

                if test_pass:
                    return view_func(request, *args, **kwargs)
                return _redirect_to_hpc_login(request)

        # Attributes used by LoginRequiredMiddleware.
        _view_wrapper.hpc_login_url = hpc_login_url
        _view_wrapper.redirect_field_name = redirect_field_name

        return wraps(view_func)(_view_wrapper)

    return decorator


def hpc_login_required(
    function=None, redirect_field_name=REDIRECT_FIELD_NAME, hpc_login_url=None
):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary.
    """
    actual_decorator = hpc_user_passes_test(
        lambda u: u.session_settings.hpc_is_connected,
        hpc_login_url=hpc_login_url,
        redirect_field_name=redirect_field_name,
    )
    if function:
        return actual_decorator(function)
    return actual_decorator



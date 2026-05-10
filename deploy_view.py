import subprocess, sys, io, os as os_mod
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import urllib.request

@csrf_exempt
def run_deploy(request):
    if request.GET.get('key') != 'deploy123':
        return HttpResponse('Forbidden', status=403)
    out = io.StringIO()
    out.write("=== Deploy started ===\n")

    project_dir = '/home/playbaby/playbaby-crm'
    git_bin = '/usr/bin/git'
    python_bin = '/home/playbaby/.virtualenvs/playbaby/bin/python'
    env = os_mod.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'lingerie_crm.settings'
    env['PYTHONPATH'] = f'{project_dir}:' + env.get('PYTHONPATH', '')

    # Step 1: git pull
    out.write("--- git pull ---\n")
    try:
        result = subprocess.run(
            [git_bin, '-C', project_dir, 'pull'],
            capture_output=True, text=True, cwd=project_dir
        )
        out.write(f"STDOUT: {result.stdout}\n")
        out.write(f"STDERR: {result.stderr}\n")
        out.write(f"Exit: {result.returncode}\n")
    except Exception as e:
        out.write(f"Error: {e}\n")

    # Step 2: migrate
    out.write("--- migrate ---\n")
    try:
        result = subprocess.run(
            [python_bin, f'{project_dir}/manage.py', 'migrate', '--verbosity', '3'],
            capture_output=True, text=True, cwd=project_dir, env=env
        )
        out.write(f"STDOUT: {result.stdout}\n")
        out.write(f"STDERR: {result.stderr}\n")
        out.write(f"Exit: {result.returncode}\n")
    except Exception as e:
        out.write(f"Error: {e}\n")

    out.write("=== Deploy complete ===\n")
    return HttpResponse(out.getvalue(), content_type='text/plain')

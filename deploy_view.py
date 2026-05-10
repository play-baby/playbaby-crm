import subprocess, io, os as os_mod
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

DEPLOY_KEY = os_mod.environ.get('DEPLOY_KEY', '')

@csrf_exempt
def run_deploy(request):
    if not DEPLOY_KEY or request.GET.get('key') != DEPLOY_KEY:
        return HttpResponse('Forbidden', status=403)
    out = io.StringIO()
    out.write("=== Deploy started ===\n")

    project_dir = '/home/playbaby/playbaby-crm'
    git_bin = '/usr/bin/git'
    python_bin = '/home/playbaby/.virtualenvs/playbaby/bin/python'
    env = os_mod.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'lingerie_crm.settings'
    env['PYTHONPATH'] = f'{project_dir}:' + env.get('PYTHONPATH', '')

    force = request.GET.get('force') == 'reset'

    if force:
        out.write("--- FORCE RESET: discarding local changes ---\n")
        result = subprocess.run(
            [git_bin, 'reset', '--hard', 'origin/main'],
            capture_output=True, text=True, cwd=project_dir
        )
        out.write(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}\nExit: {result.returncode}\n")
        result = subprocess.run(
            [git_bin, 'clean', '-fd'],
            capture_output=True, text=True, cwd=project_dir
        )
        out.write(f"Clean: {result.stdout}\n{result.stderr}\nExit: {result.returncode}\n")
        result = subprocess.run(
            [git_bin, 'stash', 'drop'],
            capture_output=True, text=True, cwd=project_dir
        )
        out.write(f"Stash drop: {result.stdout}\n{result.stderr}\nExit: {result.returncode}\n")
    else:
        # Step 1: stash any local changes
        out.write("--- git stash ---\n")
        result = subprocess.run(
            [git_bin, 'stash', 'push', '--include-untracked', '-m', 'auto-deploy-stash'],
            capture_output=True, text=True, cwd=project_dir
        )
        out.write(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}\nExit: {result.returncode}\n")

        # Step 2: git pull
        out.write("--- git pull ---\n")
        result = subprocess.run(
            [git_bin, 'pull'],
            capture_output=True, text=True, cwd=project_dir
        )
        out.write(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}\nExit: {result.returncode}\n")

        # Step 3: pop stash
        out.write("--- git stash pop ---\n")
        result = subprocess.run(
            [git_bin, 'stash', 'pop'],
            capture_output=True, text=True, cwd=project_dir
        )
        out.write(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}\nExit: {result.returncode}\n")

    # Step 4: migrate
    out.write("--- migrate ---\n")
    result = subprocess.run(
        [python_bin, f'{project_dir}/manage.py', 'migrate', '--verbosity', '3'],
        capture_output=True, text=True, cwd=project_dir, env=env
    )
    out.write(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}\nExit: {result.returncode}\n")

    out.write("=== Deploy complete ===\n")
    return HttpResponse(out.getvalue(), content_type='text/plain')

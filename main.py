import argparse
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from cybergym import Agent


def get_sed():
    try:
        subprocess.check_output(['gsed', '--version'])
        return 'gsed'
    except FileNotFoundError:
        return 'sed'


def stoml(key, config_dst):
    return subprocess.check_output(['stoml', config_dst, key]).decode().strip()


class OpenHands(Agent):
    def run(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('project')
        parser.add_argument('id')
        parser.add_argument('level')
        args = parser.parse_args()

        # Setup paths
        dir_path = Path.cwd()
        now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        short_uuid = str(uuid.uuid4())[:8]
        inst_name = f'instance-{args.project}-{args.id}-{args.level}-{now}-{short_uuid}'
        instance = dir_path / 'instances' / inst_name
        workspace = instance / 'workspace'
        config_src = dir_path / 'agents' / 'openhands' / 'config.toml'
        config_dst = instance / 'config.toml'
        prompt_path = instance / 'prompt.txt'
        sed = get_sed()

        # Create workspace
        workspace.mkdir(parents=True, exist_ok=True)
        prompt_template = dir_path / 'agents' / 'openhands' / 'prompts' / 'prompt.txt'
        prompt_level = (
            dir_path / 'agents' / 'openhands' / 'prompts' / f'lvl{args.level}.txt'
        )
        with open(prompt_path, 'w') as f:
            f.write(open(prompt_template).read())
            f.write(open(prompt_level).read())

        shutil.copy(config_src, config_dst)

        subprocess.run(
            [
                sed,
                '-i',
                f's|^workspace_base=.*|workspace_base="{workspace}"|',
                str(config_dst),
            ]
        )

        # Build files
        proj_dir = dir_path / 'projects' / args.project / args.id
        os.chdir(proj_dir)

        files_path = proj_dir / 'files'
        container_exists = subprocess.run(
            ['docker', 'ps', '-a'], capture_output=True, text=True
        )
        ex = args.id in container_exists.stdout

        file_count = len(list(files_path.iterdir())) if files_path.exists() else 0
        if file_count not in [9, 11] or not ex:
            subprocess.run(['make', 'clean-docker'])
            subprocess.run(['make'])
        else:
            subprocess.run(['make', 'clean'])
            subprocess.run(['make'])

        subprocess.run(['make', 'clean-docker'])
        subprocess.run(
            ['make', 'agent', f'LEVEL={args.level}', f'WORKSPACE={workspace}']
        )

        os.chdir(dir_path)
        shutil.copy(dir_path / 'scripts' / 'submit.sh', workspace)

        # Docker Compose
        os.makedirs(dir_path / 'traces' / args.id / args.level, exist_ok=True)

        SANDBOX_USER_ID = '0'  # Can be dynamically fetched with `os.getuid()`
        LLM_API_KEY = stoml('llm.api_key', config_dst)
        LLM_MODEL = stoml('llm.model', config_dst)

        if instance.exists():
            shutil.copy(
                dir_path / 'cybergym' / 'docker-compose.yml',
                instance / 'docker-compose.yml',
            )
            shutil.copy(
                dir_path / 'agents' / 'openhands' / '.env.template', instance / '.env'
            )

            env_path = instance / '.env'
            sed_args = [
                ('SANDBOX_USER_ID', SANDBOX_USER_ID),
                ('LLM_API_KEY', LLM_API_KEY),
                ('LLM_MODEL', LLM_MODEL),
                ('workspace', str(workspace)),
                ('instance', inst_name),
                ('build_dir', str(proj_dir)),
                ('project', args.project),
                ('id', args.id),
                ('agent', args.id),
            ]

            for key, val in sed_args:
                subprocess.run(
                    [sed, '-i', f's|^{key}=.*|{key}="{val}"|', str(env_path)]
                )

            os.chdir(instance)
            subprocess.run(['docker', 'compose', 'up', '-d'])
        else:
            print("Instance doesn't exist????")
            exit(1)

        # Run Agent
        MAX_ITER = stoml('core.max_iterations', config_dst)
        out_base = (
            dir_path / 'traces' / args.id / args.level / f'{args.id}-{now}-{short_uuid}'
        )
        cmd = [
            'poetry',
            'run',
            'python',
            '-m',
            'openhands.core.main',
            '-f',
            str(prompt_path),
            '--config-file',
            str(config_dst),
            '-i',
            MAX_ITER,
        ]

        os.chdir(dir_path / 'agents' / 'openhands')
        with open(f'{out_base}', 'w') as f_out, open(f'{out_base}.log', 'w') as f_log:
            subprocess.run(['unbuffer'] + cmd, stdout=f_out, stderr=f_log)

        os.chdir(dir_path)

        # Cleanup
        subprocess.run(['make', 'clean-docker', f'inst={instance}'])
        subprocess.run(['make', 'clean', f'instance={instance}'])

    def get_results(self):
        pass


if __name__ == '__main__':
    oh = OpenHands([])
    oh.run()

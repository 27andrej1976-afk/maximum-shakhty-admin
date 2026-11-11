"""Make an isolated deployment bundle for the existing server, without deploying."""
import argparse
from pathlib import Path
import shutil
from build_client import build

ROOT = Path(__file__).resolve().parent


def prepare(output):
    output = Path(output)
    source = output / 'app/gorod-control/region-v2'
    source.mkdir(parents=True, exist_ok=True)
    for name in ['core.py', 'events.py', 'health.py', 'collector.py', 'run_collector.py',
                 'export_feed.py', 'worker.py', 'serve.py', 'diagnose_max.py']:
        shutil.copyfile(ROOT / name, source / name)
    scripts = output / 'app/gorod-control/scripts'
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT.parent/'scripts/max_user_reader.py', scripts/'max_user_reader.py')
    shutil.copytree(ROOT/'firstvds', output/'firstvds', dirs_exist_ok=True)
    config = output/'config'
    config.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'sources.draft.json', config/'sources.json')
    shutil.copyfile(ROOT/'catalog.draft.json', config/'catalog.json')
    (output/'requirements.txt').write_text('maxapi-python==2.4.1\n')
    build(output/'public')
    (output/'DEPLOYMENT_STATUS.txt').write_text(
        'Prepared, not deployed. Source registry remains disabled.\n'
        'Requires verified catalog, incident parsing/reviews, private MAX session, server access and HTTPS routing.\n'
        'No Android release signing key or MAX session is included.\n')
    return output


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    print(prepare(p.parse_args().output))

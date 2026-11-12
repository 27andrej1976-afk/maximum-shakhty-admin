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
                 'export_feed.py', 'worker.py', 'serve.py', 'diagnose_max.py',
                 'parse_publications.py', 'pipeline.py', 'geography.py']:
        shutil.copyfile(ROOT / name, source / name)
    shutil.copyfile(ROOT/'gar-rostov-20261106.json.gz', source/'gar-rostov-20261106.json.gz')
    shutil.copyfile(ROOT/'geometry.verified.json', source/'geometry.verified.json')
    scripts = output / 'app/gorod-control/scripts'
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT.parent/'scripts/max_user_reader.py', scripts/'max_user_reader.py')
    shutil.copytree(ROOT/'firstvds', output/'firstvds', dirs_exist_ok=True)
    config = output/'config'
    config.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'sources.draft.json', config/'sources.json')
    from parse_publications import load_index
    import json
    index=load_index(ROOT/'gar-rostov-20261106.json.gz')
    (config/'catalog.json').write_text(json.dumps({'regionId':'RU-ROS','dataMode':'production',
        'municipalities':index['municipalities'],'addresses':[],
        'verification':'GAR '+index['version']},ensure_ascii=False))
    (output/'requirements.txt').write_text('maxapi-python==2.4.1\nPyNaCl==1.6.2\n')
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

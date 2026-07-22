# Copyright 2017 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import configparser
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory

from ament_flake8 import main as ament_flake8_main
from ament_flake8.main import main_with_errors
import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LINT_PATHS = [
    str(path)
    for path in (
        PACKAGE_ROOT / 'setup.py',
        PACKAGE_ROOT / PACKAGE_ROOT.name,
        PACKAGE_ROOT / 'launch',
        PACKAGE_ROOT / 'test',
    )
    if path.exists()
]


@pytest.mark.flake8
@pytest.mark.linter
def test_flake8():
    module_path = Path(
        inspect.getsourcefile(ament_flake8_main) or '',
    ).resolve()
    default_config = (
        module_path.parent
        / 'configuration'
        / 'ament_flake8.ini'
    )

    config = configparser.RawConfigParser()
    assert config.read(default_config, encoding='utf-8')
    assert config.has_section('flake8')

    existing = config.get(
        'flake8',
        'extend-ignore',
        fallback='',
    )
    ignored = {
        value.strip()
        for value in existing.split(',')
        if value.strip()
    }

    # Preserve the established tracker quote style and
    # accept summaries on the opening docstring line.
    ignored.update({'D213', 'Q000'})

    config.set(
        'flake8',
        'extend-ignore',
        ','.join(sorted(ignored)),
    )
    config.set('flake8', 'jobs', '1')

    with TemporaryDirectory(
        prefix='thesis_tracker_flake8_',
    ) as temporary_directory:
        config_path = (
            Path(temporary_directory)
            / 'ament_flake8.ini'
        )

        with config_path.open(
            'w',
            encoding='utf-8',
        ) as stream:
            config.write(stream)

        rc, errors = main_with_errors(
            argv=[
                '--config',
                str(config_path),
                *LINT_PATHS,
            ]
        )

    assert rc == 0, (
        'Found %d code style errors / warnings:\n' % len(errors)
        + '\n'.join(errors)
    )

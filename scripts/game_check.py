#!/usr/bin/env python3
"""Basic container and executable validation for source-only game experiments."""
import hashlib
import struct
import sys
from pathlib import Path


def sfo_info(game):
    from prepare import sfo
    try:
        return sfo((Path(game) / 'sce_sys' / 'param.sfo').read_bytes())
    except (OSError, ValueError, IndexError, struct.error):
        return {}


def executable_path(game):
    game = Path(game)
    elf = game / 'eboot.elf'
    return elf if elf.is_file() else game / 'eboot.bin'


def split_layout(game):
    game = Path(game)
    return (game / 'Image0' / 'eboot.bin').is_file() and not (game / 'sce_module').is_dir()


def image_sha256(game):
    from prepare import parse_self, span
    elf, _header, ph, _segments, _missing = parse_self(executable_path(game).read_bytes())
    loads = [p for p in ph if p['type'] in (1, 0x61000010)]
    if not loads:
        raise ValueError('executable has no loadable segments')
    image = bytearray(max(p['vaddr'] + p['memsz'] for p in loads))
    for segment in loads:
        image[segment['vaddr']:segment['vaddr'] + segment['filesz']] = span(
            elf, segment['offset'], segment['filesz'])
    return hashlib.sha256(image).hexdigest()


def problem(game, _image_hash=None):
    if split_layout(game):
        return 'split_layout', '?', '?'
    info = sfo_info(game)
    title, version = info.get('TITLE_ID', '?'), info.get('APP_VER', '?')
    try:
        image_sha256(game)
    except (OSError, ValueError, IndexError, StopIteration, KeyError, struct.error):
        return 'unreadable', title, version
    return None


def profile(game, _image_hash=None):
    found = problem(game)
    if found:
        return None
    info = sfo_info(game)
    return dict(name='generic', title=info.get('TITLE_ID', 'unknown'),
                version=info.get('APP_VER', 'unknown'), game='Unclassified PS4 title',
                modules=('libc.prx', 'libSceFios2.prx'), patches=False, variant='source-only')


def explain(kind, title, version):
    found = f'Found {title} version {version} (sce_sys/param.sfo).'
    return {
        'split_layout': 'The game folder has the PS4 PKG Tool layout (Image0 and Sc0); prepare or '
                        'flatten the package before running it.',
        'unreadable': f'{found} eboot.bin is not a readable decrypted PS4 executable. '
                      'Use the locally decrypted ELF as eboot.bin in a private game-folder copy.',
    }[kind]


if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:1] == ['--info']:
        info = sfo_info(Path(args[1]) if len(args) > 1 else Path('.'))
        print(info.get('TITLE_ID', 'CUSA12112'), info.get('APP_VER', '01.00'))
        sys.exit()
    game = Path(args[0]) if args else Path('.')
    found = problem(game)
    if found:
        sys.exit('Game check failed: ' + explain(*found))
    print('generic')

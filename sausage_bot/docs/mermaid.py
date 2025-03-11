#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'mermaid: converting mermaid charts to images'
import base64
import os
import requests
from tqdm import tqdm

from sausage_bot.util import envs
from sausage_bot.util.log import log


def download_file(url, file_out):
    '''
    Download a file

    Parameters
    ------------
    url: str
        url to download (default: None)
    file_out: str
        filename to save to (default: None)
    '''
    if url is None or file_out is None:
        log.log('Missing parameters')
        return None
    file_size = int(requests.head(url).headers["Content-Length"])
    if os.path.exists(file_out):
        first_byte = os.path.getsize(file_out)
    else:
        first_byte = 0
    if first_byte >= file_size:
        return file_size
    header = {"Range": "bytes=%s-%s" % (first_byte, file_size)}
    pbar = tqdm(
        total=file_size, initial=first_byte,
        unit='B', unit_scale=True, desc=url.split('/')[-1]
    )
    req = requests.get(url, headers=header, stream=True)
    with open(file_out, 'ab') as f:
        for chunk in req.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                pbar.update(1024)
    pbar.close()
    return file_size


def mermaid(graph):
    """
    Generates image link for mermaid chart
    """
    log.debug('Making image link...')
    graphbytes = graph.encode("utf-8")
    base64_bytes = base64.urlsafe_b64encode(graphbytes)
    base64_string = base64_bytes.decode("utf-8")
    return f'https://mermaid.ink/img/{base64_string}'


def check_and_convert_graph(file):
    log.debug(f'Checking `{file}`')
    chart_content = open(
        f'{envs.MERMAID_DIR}/{file}', "r"
    ).read().replace('```mermaid\n', '').replace('\n```', '')
    chart_link = mermaid(chart_content)
    filename = file.split('.')[0]
    log.debug(f'Downloading file ({chart_link})...')
    download_file(chart_link, f'{envs.MERMAID_DIR}/{filename}.png')


if __name__ == "__main__":
    for file in os.listdir(envs.MERMAID_DIR):
        if file.endswith('.png'):
            os.remove(f'{envs.MERMAID_DIR}/{file}')
    for file in os.listdir(envs.MERMAID_DIR):
        if file.endswith('.mermaid'):
            check_and_convert_graph(file)

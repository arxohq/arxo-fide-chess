#!/usr/bin/env python3
"""Independent stdlib checks of the actual OCI archive and container policy."""
import hashlib
import json
from pathlib import PurePosixPath
import re
import tarfile


def image_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',value):
        raise ValueError('Invalid immutable Docker image ID')
    return value


def archive_image_id(path, expected):
    """Never trust a previously cached local image to identify an incoming archive."""
    image_id(expected)
    with tarfile.open(path,'r:*') as archive:
        members=archive.getmembers()
        def member(name):
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('Unsafe Docker archive path')
            found=[m for m in members if m.name==name]
            if len(found)!=1 or not found[0].isfile() or found[0].size>2*1024*1024:raise ValueError('Docker manifest/config must be unique bounded regular files')
            return archive.extractfile(found[0]).read()
        manifest=json.loads(member('manifest.json'))
        if not isinstance(manifest,list) or len(manifest)!=1 or not isinstance(manifest[0],dict):raise ValueError('Docker archive must contain exactly one image')
        config=member(manifest[0]['Config'])
        observed='sha256:'+hashlib.sha256(config).hexdigest()
        if observed!=expected:raise ValueError('Docker archive config identity differs from accepted image (cached images cannot substitute)')
        if not isinstance(json.loads(config),dict):raise ValueError('Docker image config is malformed')
    return observed


def options(text):
    if not isinstance(text,str):raise ValueError('Tmpfs policy must be an actual option string')
    result={}
    for item in text.split(','):
        key,sep,value=item.partition('=')
        if not key or key in result:raise ValueError('Ambiguous tmpfs policy')
        result[key]=value if sep else True
    return result


def size(text):
    match=re.fullmatch(r'([0-9]+)([kmgt]?)(?:b)?',str(text).lower())
    if not match:raise ValueError('Invalid bounded tmpfs size')
    return int(match[1])*(1024**('kmgt'.find(match[2])+1) if match[2] else 1)


def validate_container_policy(policy, expected_image):
    image_id(expected_image)
    if not isinstance(policy,dict) or policy.get('Image')!=expected_image:raise ValueError('Container policy is not bound to the built immutable image')
    host=policy.get('HostConfig');config=policy.get('Config')
    if not isinstance(host,dict) or not isinstance(config,dict):raise ValueError('Malformed actual container policy')
    if host.get('NetworkMode')!='none' or host.get('ReadonlyRootfs') is not True or host.get('Privileged') is not False:raise ValueError('Container network/filesystem/privilege isolation is weakened')
    if config.get('User')!='65532:65532':raise ValueError('Container must use declared unprivileged UID/GID')
    if not isinstance(host.get('CapDrop'),list) or 'ALL' not in [str(c).upper() for c in host['CapDrop']] or host.get('CapAdd'):raise ValueError('Container capabilities are not fully dropped')
    security=host.get('SecurityOpt')
    if not isinstance(security,list) or not any(v in ('no-new-privileges','no-new-privileges:true') for v in security):raise ValueError('Container can acquire new privileges')
    for key,ceiling in [('Memory',512*1024*1024),('PidsLimit',128),('NanoCpus',1000000000)]:
        value=host.get(key)
        if not isinstance(value,int) or isinstance(value,bool) or not 0<value<=ceiling:raise ValueError('Container limit absent or exceeded: '+key)
    temporary=host.get('Tmpfs')
    if not isinstance(temporary,dict) or set(temporary)!= {'/state','/tmp'}:raise ValueError('Container writable paths differ from declared bounded tmpfs')
    for path,ceiling in [('/state',64*1024*1024),('/tmp',8*1024*1024)]:
        opt=options(temporary[path])
        if not all(opt.get(flag) is True for flag in ('rw','noexec','nosuid','nodev')):raise ValueError('Tmpfs hardening absent: '+path)
        if not 0<size(opt.get('size',''))<=ceiling:raise ValueError('Tmpfs size absent or exceeded: '+path)
        if path=='/state':
            if opt.get('uid')!='65532' or opt.get('gid')!='65532' or not re.fullmatch(r'0?700',str(opt.get('mode',''))):raise ValueError('State ownership/mode differs from declared policy')
    mounts=policy.get('Mounts')
    if not isinstance(mounts,list) or any(m.get('Type')!='tmpfs' or m.get('Destination') not in ('/state','/tmp') for m in mounts):raise ValueError('Unexpected external runtime mount')
    return True


def validate_registry_manifest(manifest, expected_image):
    image_id(expected_image)
    if not isinstance(manifest,dict) or manifest.get('schemaVersion')!=2 or 'manifests' in manifest:
        raise ValueError('Released registry digest must name a single-platform image manifest')
    if manifest.get('config',{}).get('digest')!=expected_image:
        raise ValueError('Registry manifest config differs from the actually smoked image')
    return True

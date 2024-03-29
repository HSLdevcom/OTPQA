from __future__ import print_function

import json
import os
import grequests
import requests
import sys
import pprint

import unicodecsv
import numpy as np
import gen_requests
import cluster_places

token = os.getenv('PIWIK_TOKEN', None)

assert token, "Token is none"

piwik_baseurl = os.getenv('PIWIK_URL', 'https://digiaiiris.com/web-analytics')

period = 'month'

client_cert = 'client.pem'

sites_router = {
    '4': {'name': 'reittiopas.hsl.fi', 'feed': 'HSL', 'router': ('hsl','finland'), 'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '11': {'name': 'joensuu.digitransit.fi', 'feed': 'Joensuu', 'router': ('waltti','finland'), 'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '27': {'name': 'turku.digitransit.fi', 'feed': 'FOLI', 'router': ('waltti','finland'), 'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '14': {'name': 'hameenlinna.digitransit.fi', 'feed': 'Hameenlinna', 'router': ('waltti','finland'), 'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '15': {'name': 'jyvaskyla.digitransit.fi', 'feed': 'LINKKI', 'router': ('waltti','finland'), 'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '16': {'name': 'kuopio.digitransit.fi', 'feed': 'Kuopio', 'router': ('waltti','finland'), 'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '17': {'name': 'lahti.digitransit.fi', 'feed': 'Lahti', 'router': ('waltti','finland'), 'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '18': {'name': 'lappeenranta.digitransit.fi', 'feed': 'Lappeenranta', 'router': ('waltti','finland'), 'eps': 250, 'min_samples': 2, 'hits_percentile': 40},
    '21': {'name': 'oulu.digitransit.fi', 'feed': 'Oulu', 'router': ('waltti','finland'),'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '29': {'name': 'kotka.digitransit.fi', 'feed': 'Kotka', 'router': ('waltti','finland'),'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '31': {'name': 'mikkeli.digitransit.fi', 'feed': 'Mikkeli', 'router': ('waltti','finland'),'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '35': {'name': 'tampere.digitransit.fi', 'feed': 'tampere', 'router': ('waltti','finland'),'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '43': {'name': 'kouvola.digitransit.fi', 'feed': 'Kouvola', 'router': ('waltti','finland'),'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
    '49': {'name': 'rovaniemi.digitransit.fi', 'feed': 'Rovaniemi', 'router': ('waltti','finland'),'eps': 100, 'min_samples': 2, 'hits_percentile': 50},
}

router_sites = {}

sitesurl = '%(baseurl)s/?module=API&method=SitesManager.getSitesWithAtLeastViewAccess&format=JSON&token_auth=%(token)s' % {
    'baseurl': piwik_baseurl, 'token': token}
r = requests.get(sitesurl, cert=client_cert)
piwiksites = r.json()
r.close()

for psite in piwiksites:
    siteid = psite['idsite']
    if not siteid in sites_router:
        continue

    siteinfo = sites_router[siteid]
    routers = siteinfo['router']
    for router in routers:
        if not router in router_sites:
            router_sites[router] = []

        siteinfo['idsite'] = psite['idsite']
        router_sites[router].append(siteinfo)


def clean_label(label):
    label = label.strip('/')
    return label[:label.find('?')]


def parse_place(place):
    try:
        name, coords = place.split('::')
        lat, lon = map(float, coords.split(','))
    except ValueError:
        return None
    return dict(name=name, lat=lat, lon=lon)


def response_callback_factory(places, label, idsubdatatable, hits):
    fromp = parse_place(label)
    def handle_response(response, *args, **kwargs):
        if response.status_code != 200:
            status = 'failed'
            return None

        tourls = response.json()

        for tu in tourls:
            if tu['label'] == 'Others':
                continue

            if tu['label'].strip() == '':
                continue

            tolabel = clean_label(tu['label'])

            tohits = tu['nb_hits']
            top = parse_place(tolabel)

            if fromp and top:
                if tolabel in places:
                    places[tolabel] += tohits
                else:
                    places[tolabel] = tohits
        response.connection.close()
        #print(idsubdatatable, label, hits, response)

    return handle_response


for router in router_sites:
    rsites = router_sites[router]
    print(router)
    router_endpoints = []
    router_clustered_endpoints = []
    for site in rsites:
        print(site['name'],'/',site['idsite'])
        site_places = {}

        siteid = site['idsite']

        url = '%(baseurl)s/?module=API&method=Actions.getPageUrls&idSite=%(siteid)s&period=%(period)s&date=today&format=JSON&token_auth=%(token)s&filter_column=label&filter_pattern=^reitti$' % {
            'baseurl': piwik_baseurl, 'siteid': siteid, 'period': period, 'token': token}

        r = requests.get(url, cert=client_cert)
        pageurls = r.json()
        r.close()

        if len(pageurls) == 0 or pageurls[0]['label'] != 'reitti':
            print('Retrieving page url for reitti-pages failed for sited %s' % siteid)
            continue

        reitti_page = pageurls[0]

        idsubtable = reitti_page['idsubdatatable']

        subdataurl = '%(baseurl)s/?module=API&method=Actions.getPageUrls&idSite=%(siteid)s&period=%(period)s&date=today&format=JSON&token_auth=%(token)s&filter_limit=5000&idSubtable=%(idsubtable)s' % {
            'baseurl': piwik_baseurl, 'idsubtable': idsubtable, 'period': period, 'siteid': siteid, 'token': token}

        r = requests.get(subdataurl, cert=client_cert)
        frompageurls = r.json()
        r.close()

        reqs = []

        for fpu in frompageurls:
            if fpu['label'] == 'Others':
                continue
            if 'idsubdatatable' not in fpu:
                continue
            if fpu['label'].strip() == '':
                continue
            label = clean_label(fpu['label'])
            idsubdatatable = fpu['idsubdatatable']
            hits = fpu['nb_hits']

            site_places[label] = hits

            url = '%(baseurl)s/?module=API&method=Actions.getPageUrls&idSite=%(siteid)s&period=%(period)s&date=today&format=JSON&token_auth=%(token)s&filter_limit=5000&idSubtable=%(idsubtable)s' % {
                'baseurl': piwik_baseurl, 'idsubtable': idsubdatatable, 'period': period, 'siteid': siteid,
                'token': token}

            response_callback = response_callback_factory(site_places, label, idsubdatatable, hits)
            headers = {'Accept': 'application/json'}
            req = grequests.get(url, cert=client_cert, headers=headers, hooks=dict(response=response_callback))
            reqs.append(req)


        def exception_handler(request, exception):
            raise exception

        res = grequests.imap(reqs, size=20, exception_handler=exception_handler)
        for i,_ in enumerate(res):
            pass

        print(i,'requests done')

        endpoints = []
        for rawplace in sorted((p[1], p[0]) for p in site_places.items()):
            place = parse_place(rawplace[1])
            if place is not None:
                endpoints.append({'name': place['name'], 'lat': place['lat'], 'lon': place['lon'], 'hits': rawplace[0]})


        clustered_endpoints = cluster_places.clusterEndpoints(endpoints,
                                                              eps=site['eps'],
                                                              min_samples=site['min_samples'])

        nphits = np.array([ep['hits'] for ep in clustered_endpoints], dtype=np.uint32)
        hits_limit = np.percentile(nphits, site['hits_percentile'])
        print('HITS MIN:', hits_limit)

        clustered_endpoints = [ep for ep in clustered_endpoints if ep['hits'] > hits_limit]

        router_endpoints += endpoints
        router_clustered_endpoints += clustered_endpoints

        qarequests = gen_requests.generateRequestsFromEndpoints(clustered_endpoints)

        site['requests'] = qarequests

        # pprint.pprint(qarequests)

    f = open('%s_original_test.csv' % router, 'wb')
    w = unicodecsv.writer(f, encoding='utf-8')
    w.writerow(('name', 'lon', 'lat','hits'))

    for ep in router_endpoints:
        w.writerow((ep['name'], ep['lon'], ep['lat'],ep['hits']))
    f.close()

    f = open('%s_clustered_test.csv' % router, 'wb')
    w = unicodecsv.writer(f, encoding='utf-8')
    w.writerow(('name', 'lon', 'lat','hits'))
    for ep in router_clustered_endpoints:
        # print(ep)
        w.writerow((ep['name'], ep['lon'], ep['lat'], ep['hits']))
    f.close()


f = open('otpqa_router_requests.json','w+')
json.dump(router_sites,f)
f.close()

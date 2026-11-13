import json
import unittest
from pathlib import Path
from parse_publications import Templates,load_index
import test_real_pipeline as real
from pipeline import process

ROOT=Path(__file__).parent

class AddressParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index=load_index(ROOT/'gar-rostov-20261106.json.gz');cls.t=Templates(cls.index)
        cls.cases=json.loads((ROOT/'testdata/address-cases-20261113.json').read_text())['publications']

    def test_actual_dot_spacing_initial_and_surname(self):
        for city,body,names in [('г. Морозовск','ул.Тельмана, ул.К Маркса',['Тельмана','Карла Маркса']),
                               ('г. Ростов-на-Дону','просп.Нагибина',['Михаила Нагибина'])]:
            found,unknown=self.t.addresses(body,self.t.city(city))
            self.assertEqual(unknown,[]);self.assertEqual({a['name'] for a in found},set(names))
        self.assertEqual(self.t.city('ст.Тацинская')['name'],'Тацинская')

    def test_numeric_street_name_is_not_a_house_but_tail_is(self):
        city=self.t.city('г. Белая Калитва')
        a,u=self.t.addresses('ул.1-я линия',city);self.assertEqual(u,[]);self.assertFalse(a[0]['houseRangeSpecified'])
        a,u=self.t.addresses('ул.1-я линия 12-18',city);self.assertTrue(a[0]['houseRangeSpecified'])

    def test_ambiguous_alias_is_not_resolved(self):
        index={'version':'test','municipalities':[{'id':'a','name':'Тест'}],
          'streets':[{'id':str(i),'municipalityId':'a','type':'ул.','name':n} for i,n in enumerate(['Ивана Иванова','Петра Иванова'])]}
        t=Templates(index);a,u=t.addresses('ул.Иванова',index['municipalities'][0]);self.assertEqual(a,[]);self.assertEqual(len(u),1)

    def test_real_unlocated_water_is_not_mapped_as_affected_district(self):
        p=next(p for p in self.cases if p['sourceId']=='ursv')
        plan=self.t.propose(p,{'categories':['water']});self.assertEqual(plan['state'],'pending');self.assertNotIn('addresses',plan)

    def test_real_current_power_formats_produce_locality_bound_addresses(self):
        for p in self.cases:
            if p['sourceId']!='donenergo':continue
            plan=self.t.propose(p,{'categories':['power']});self.assertEqual(plan['state'],'incident',p['id'])
            self.assertTrue(plan['addresses']);self.assertTrue(all(a['municipalityId']==plan['city']['id'] for a in plan['addresses']))

    def test_real_water_pressure_explicit_streets_and_postfix_types(self):
        post=json.loads((ROOT/'testdata/water-pressure-20261113.json').read_text())
        plan=self.t.propose(post,{'categories':['water']})
        self.assertEqual(plan['state'],'incident');self.assertEqual(plan['title'],'Снижение давления · Шахты')
        self.assertEqual(len(plan['addresses']),9);self.assertEqual(plan['unresolvedAddresses'],[])
        self.assertNotIn('Тимирязева',{a['name'] for a in plan['addresses']},'repair cause is not an affected address')
        self.assertEqual(plan['end'],'2026-11-13T17:00:00+03:00')
        from offline_geography import load_offline_points,NAME
        points=load_offline_points(ROOT/NAME,self.index)
        self.assertTrue(all(a['id'] in points for a in plan['addresses']))

    def test_address_only_amendment_preserves_original_hash_and_expiry(self):
        real.RealPipelineTests.setUpClass();case=real.RealPipelineTests();case.setUp()
        try:
            ledger,_=process(case.store,case.catalog,case.index,'2026-11-12T13:00:00+00:00',geometry=case.geometry)
            row=case.store.db.execute("SELECT id,payload FROM reviewed_events WHERE json_extract(payload,'$.category')='power'").fetchone()
            original=json.loads(row[1]);reduced=dict(original,addressIds=original['addressIds'][:-1],unresolvedAddresses=['ул. '+ledger.addresses[original['addressIds'][-1]]['name']],parserVersion='source-templates-gar-v1')
            with case.store.db:
                case.store.db.execute('UPDATE reviewed_events SET payload=? WHERE id=?',(json.dumps(reduced),row[0]))
                case.store.db.execute('UPDATE review_log SET payload=? WHERE id=?',(json.dumps(reduced),original['reviewId']))
            before=next(e for e in ledger.events('2026-11-12T13:00:00+00:00') if e['category']=='power')
            ledger,_=process(case.store,case.catalog,case.index,'2026-11-12T13:01:00+00:00',geometry=case.geometry)
            after=next(e for e in ledger.events('2026-11-12T13:01:00+00:00') if e['category']=='power')
            self.assertEqual(len(after['addresses']),len(original['addressIds']));self.assertEqual(before['expiresAt'],after['expiresAt'])
            self.assertEqual(before['sourceHash'],after['sourceHash']);self.assertEqual(after['unresolvedAddresses'],[])
            self.assertEqual(json.loads(case.store.db.execute('SELECT payload FROM reviewed_events WHERE id=?',(row[0],)).fetchone()[0]),reduced)
            bad=dict(original,start='2026-11-12T12:00:00+00:00')
            with self.assertRaises(ValueError):ledger.enrich_addresses(bad,'2026-11-12T13:01:00+00:00')
        finally:case.tearDown()

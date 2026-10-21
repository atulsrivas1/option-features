"""Independent exact-wire R25 fixture candidates. Never imports production.

Execution requires coordinator resource clearance. Source inspection is harmless.
External review receipt, not this generator, authorizes reviewed-candidate state.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import sys

AUTHOR = '/root/r25_independent_wire_fixtures'
YEAR_NS = 365 * 86400 * 10**9
NOW = 10**15
PRECISIONS = (80, 140)
UNITS = {'contract.dte': 'calendar_days', 'contract.multiplier': 'underlying_units_per_contract',
         'contract.moneyness': 'strike_spot_ratio', 'liquidity.spread_bps': 'bps',
         'quality.quote_coverage': 'ratio', 'chain.activity': 'score',
         'pricing.price': 'currency_per_underlying_payoff_unit', 'greeks.delta': 'absolute_delta',
         'greeks.signed_delta': 'signed_delta', 'greeks.gamma': 'inverse_currency',
         'greeks.vega': 'currency_per_unit_sigma', 'greeks.rho': 'currency_per_unit_rate',
         'greeks.theta': 'currency_per_year', 'volatility.implied_volatility': 'annual_decimal_volatility'}
MODEL_OUTPUTS = tuple(k for k in UNITS if k.startswith('greeks.') or k == 'pricing.price')
OMISSIONS = [
    'Method-instrumentation evidence for rescue probes, unresolved cap/midpoint comparisons and full finite-work accounting remains separate.',
    'No claimed rigorous mpmath transcendental error bound; two-precision semantic side decisions are reviewed empirical oracle evidence.',
    'Overflow reason without an explicit range guard is not fixed by normative prose and is not invented here.',
    'No claim of Linux validation, provider completeness, or correctly rounded 65-digit oracle values.',
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def record_digest(kind, row):
    return hashlib.sha256(('option-record1\n'+kind+'\n').encode()+canonical(row)).hexdigest()


def rational_text(value):
    v = Fraction.from_float(value) if isinstance(value, float) else Fraction(value)
    return str(v.numerator)+'/'+str(v.denominator)


def base(side='call', S='100', K='100', rate=0.0, carry=0.0, sigma=0.25, years=1, multiplier='100'):
    fixing = NOW + int(Fraction(years)*YEAR_NS)
    binding = {'binding_id': 'original-synthetic', 'source_id': 'original-r25-wire-fixtures',
               'source_revision': '1', 'source_content_sha256': hashlib.sha256(b'original synthetic fixture specification v1').hexdigest(),
               'provenance_mode': 'synthetic', 'rights_reference': 'Original synthetic examples; no external market data'}
    definition = dict(contract_id='OPT', underlying_id='UND', right=side, strike=K, currency='USD',
                      multiplier=multiplier, deliverable='scalar_underlying', action_basis_id='unadjusted',
                      exercise='european', model_profile_admission='certified_vanilla_continuous_carry',
                      settlement='cash', last_trade_ns=fixing, fixing_ns=fixing, payment_ns=fixing,
                      expiry_ordinal=738001, timezone_id='synthetic-fixed', civil_binding_id='civil',
                      revision_id='definition-1', effective_from_ns=0, effective_to_ns=None,
                      known_at_ns=0, input_binding_id='original-synthetic')
    spot = dict(underlying_id='UND', value=S, currency='USD', action_basis_id='unadjusted', event_ns=NOW,
                known_at_ns=NOW, revision_id='spot-1', input_binding_id='original-synthetic')
    facts = [dict(underlying_id='UND', contract_id='OPT' if kind == 'volatility' else None,
                  kind=kind, value=value, model_id='option-bsm1', currency='USD', action_basis_id='unadjusted',
                  effective_from_ns=0, effective_to_ns=None, known_at_ns=0, revision_id=kind+'-1',
                  input_binding_id='original-synthetic') for kind, value in [('rate',rate),('carry',carry),('volatility',sigma)]]
    civil = [dict(civil_binding_id='civil', instant_ns=t, ordinal=o, timezone_id='synthetic-fixed',
                  known_at_ns=0, input_binding_id='original-synthetic') for t,o in [(NOW,738000),(fixing,738001)]]
    if fixing == NOW:
        civil = [civil[0]]
        definition['expiry_ordinal'] = 738000
    snap = dict(schema_version='option-canonical1', bindings=[binding], civil_bindings=civil,
                definitions=[definition], spots=[spot], model_facts=facts, quotes=[], supplied_metrics=[],
                trades=[], coverage_certificates=[], quote_coverage_windows=[], activity_window=None)
    req = dict(schema_version='option-request1', contract_ids=['OPT'], output_ids=list(MODEL_OUTPUTS),
               origin_policy='computed_only', supplied_delta_policy='exact_only', valuation_ns=NOW,
               knowledge_cutoff_ns=NOW, valuation_ordinal=738000, civil_binding_id='civil', model_id='option-bsm1',
               formula_version='r25-formulas1', eligibility=dict(max_quote_age_ns=1000, max_spot_age_ns=1000,
               max_supplied_metric_age_ns=1000), solver=dict(method='bisection1',quote_basis='midpoint',
               max_sigma=8.0,max_iterations=256,price_abs_tol=1e-10,price_rel_tol=1e-10,vol_abs_tol=1e-10,vol_rel_tol=1e-10),
               limits=dict(max_wire_bytes=16777216,max_snapshot_records=100000,max_requested_contracts=1000,
               max_selected_outputs=32,max_result_rows=32001,max_solver_iterations=4096))
    return snap, req


def quote(bid, ask):
    return dict(contract_id='OPT',sample_id=None,bid=bid,ask=ask,currency='USD',
                price_basis='per_underlying_payoff_unit',event_ns=NOW,known_at_ns=NOW,sequence=0,
                revision_id='quote-1',input_binding_id='original-synthetic')


def deps(snapshot, groups):
    # Explicit per-case dependency selection, never production traversal.
    return [(kind,row) for key,kind in groups for row in snapshot[key]]


DEFINITION = [('definitions','definition')]
SPOT = [('spots','spot')]
FACTS = [('model_facts','model_fact')]
QUOTE = [('quotes','quote')]


def expected(output, value, dependencies, status='available', reason='ok', flags=(),
             origin='computed', producer=None, uncertainty='0', coverage=None, solver_assertions=None):
    reference = output.startswith('contract.') or output.startswith('liquidity.') or output.startswith('quality.') or output == 'chain.activity'
    formula = ('option-reference1' if output.startswith('contract.') else
               'option-spread1' if output.startswith('liquidity.') else
               'option-quote-count1' if output.startswith('quality.') else
               'option-chain-breadth1' if output == 'chain.activity' else 'option-bsm1')
    model = 'not_applicable' if reference else 'option-bsm1'
    if producer:
        model = producer[0]
        formula = 'option-absolute-delta1' if origin == 'computed' else producer[1]
    return dict(output_id=output,contract_id=None if output=='chain.activity' else 'OPT',underlying_id='UND',
                status=status,reason=reason,unit=UNITS[output],origin=origin,model_id=model,formula_version=formula,
                producer_model_id=None if producer is None else producer[0],
                producer_formula_id=None if producer is None else producer[1],quality_flags=sorted(flags),
                dependency_binding_ids=sorted({row['input_binding_id'] for _,row in dependencies}),
                dependency_record_sha256s=sorted({record_digest(kind,row) for kind,row in dependencies}),
                oracle_decimal=None if value is None else str(value),relative_tolerance='1e-10',absolute_tolerance='0',
                oracle_uncertainty=uncertainty,coverage=coverage,
                solver_assertions=solver_assertions if solver_assertions is not None else
                    dict(presence='not_fixed_by_contract') if output=='volatility.implied_volatility' else dict(presence='absent'),
                require_pricing_enclosure=(output=='pricing.price' and status=='available'))


def artifact_cases(contexts, oracle):
    cases=[]
    high=contexts[-1]
    def add(name,families,snapshot,request,wanted,derivation):
        cases.append(dict(id=name,families=families,operand_domain='exact_wire_decimal_and_binary64_ratios',
                          snapshot_payload=snapshot,request_payload=request,expected=wanted,derivation=derivation))
    def two_values(snap):
        d=snap['definitions'][0]; s=snap['spots'][0]['value']
        f={x['kind']:x['value'] for x in snap['model_facts']}
        operands=[s,d['strike'],rational_text(f['rate']),rational_text(f['carry']),rational_text(f['volatility']),
                  rational_text(Fraction(d['fixing_ns']-NOW,YEAR_NS))]
        return [oracle.interior(ctx,d['right'],operands) for ctx in contexts]
    def numeric_wanted(output, values, dependencies):
        lo=high.mpf(contexts[0].nstr(values[0],82)); hi=values[1]
        oracle.agree(high,lo,hi,'1e-60','0',output+' exact-wire precision agreement')
        text=high.nstr(hi,65,strip_zeros=False)
        # Empirical two-precision budget plus retained-digit rounding allowance;
        # not a true transcendental enclosure or all-digit rounding guarantee.
        uncertainty=high.nstr(abs(hi)*high.mpf('1e-60')+abs(hi-high.mpf(text)),65)
        return expected(output,text,dependencies,uncertainty=uncertainty)
    def iv_condition_flags(snapshot,request,roots,extra=()):
        """Apply frozen conditioning inequality independently in each context.

        The mathematical root is the oracle operand. Candidate displacement is
        narrower than the independently selected volatility regression budget;
        fixtures require a wide margin rather than infer a borderline flag.
        """
        d=snapshot['definitions'][0]
        facts={row['kind']:row['value'] for row in snapshot['model_facts']}
        target=(Fraction(Decimal(snapshot['quotes'][0]['bid']))+Fraction(Decimal(snapshot['quotes'][0]['ask'])))/2
        decisions=[];vegas=[]
        for ctx,root in zip(contexts,roots):
            S,K,r,q,T=[oracle.rational(ctx,x) for x in (snapshot['spots'][0]['value'],d['strike'],rational_text(facts['rate']),
                rational_text(facts['carry']),rational_text(Fraction(d['fixing_ns']-NOW,YEAR_NS)))]
            A=S*ctx.exp(-q*T);B=K*ctx.exp(-r*T)
            if root==0:
                # Right-sigma derivative at a lower-bound zero-vol root.
                vega=A*ctx.sqrt(T)/ctx.sqrt(2*ctx.pi) if S==K and r==q else ctx.mpf(0)
            else:
                z=root*ctx.sqrt(T)
                d1=(ctx.log(S/K)+(r-q+root*root/2)*T)/z
                vega=A*ctx.exp(-d1*d1/2)/ctx.sqrt(2*ctx.pi)*ctx.sqrt(T)
            vegas.append(vega)
            cfg=request['solver']
            p_budget=oracle.rational(ctx,rational_text(cfg['price_abs_tol']))+oracle.rational(ctx,rational_text(cfg['price_rel_tol']))*abs(oracle.rational(ctx,rational_text(target)))
            v_budget=oracle.rational(ctx,rational_text(cfg['vol_abs_tol']))+oracle.rational(ctx,rational_text(cfg['vol_rel_tol']))*abs(root)
            difference=p_budget-abs(vega)*v_budget
            if abs(difference)<=max(p_budget,abs(vega)*v_budget)*ctx.mpf('1e-40'):
                raise ArithmeticError('conditioning flag too close to empirical boundary')
            decisions.append(difference>=0)
        if decisions[0]!=decisions[1]:raise ArithmeticError('conditioning decision changes across precision')
        oracle.agree(high,high.mpf(contexts[0].nstr(vegas[0],82)),vegas[1],'1e-60','0','independent IV Vega')
        return dict(quality_flags=sorted(set(extra)|({'ill_conditioned'} if decisions[0] else set())),
                    ill_conditioned=decisions[0],oracle_vega=high.nstr(vegas[1],65,strip_zeros=False))

    inventory=[('atm','100','100',0.0,0.0,2.0,1),('carry','103','97',0.03,0.01,0.25,Fraction(3,2)),
               ('negative','91','109',-0.02,-0.03,0.4,2),('short','101','100',0.01,0.0,0.3,Fraction(1,365)),
               ('long','100','102',0.04,0.02,0.1,10),('itm','150','100',0.0,0.01,0.25,1),
               ('otm','75','120',0.01,0.0,0.25,1)]
    for name,S,K,r,q,v,T in inventory:
        for right in ('call','put'):
            s,rq=base(right,S,K,r,q,v,T)
            vals=two_values(s)
            dd=deps(s,DEFINITION+SPOT+FACTS)
            wanted=[numeric_wanted(k,[x[k] for x in vals],dd) for k in rq['output_ids']]
            add(name+'-'+right,['interior','units'],s,rq,wanted,'Independent erfc price, erf Greeks, derivatives, finite differences and parity at exact wire operands.')
    # Symbolic endpoints independently reduce each formula; endpoint-specific
    # dependencies intentionally do not include irrelevant rate/carry/sigma.
    for right in ('call','put'):
        for S in ('90','100','110'):
            for sigma,T in ((0.0,0),(0.25,0),(0.0,1)):
                s,rq=base(right,S,sigma=sigma,years=T)
                vv=[oracle.endpoint(ctx,right,S,rational_text(sigma),str(T)) for ctx in contexts]
                wanted=[]
                for k in rq['output_ids']:
                    groups=DEFINITION+SPOT
                    if T:
                        groups+=FACTS
                    elif k in ('greeks.vega','greeks.rho'):
                        groups=DEFINITION
                    dd=deps(s,groups)
                    if not T and k=='greeks.theta':
                        itm=(1 if right=='call' else -1)*(Decimal(S)-100)>0
                        kinds={'rate','carry'} if itm else set()
                        if S=='100':kinds={'volatility'} | ({'rate','carry'} if sigma==0 else set())
                        dd += [('model_fact',row) for row in s['model_facts'] if row['kind'] in kinds]
                    if k in vv[0][1]:
                        st,reason=vv[0][1][k]
                        wanted.append(expected(k,None,dd,st,reason,[reason]))
                    else:
                        wanted.append(numeric_wanted(k,[x[0][k] for x in vv],dd))
                add('endpoint-'+right+'-'+S+'-'+str(sigma)+'-'+str(T),['terminal' if T==0 else 'zero_volatility'],s,rq,wanted,
                    'Separate symbolic endpoint formulas from original oracle; dependency branch audit required before acceptance.')
    # IV exact bounds use r=q=0, S110/K100: L10/U110 for call.
    for name,target,status,reason,value,flags in [
        ('lower','10','available','ok','0',['lower_boundary']),
        ('upper','110','nonidentifiable_inverse','upper_asymptote',None,['upper_asymptote']),
        ('below','9.999999999999999999','invalid_input','price_out_of_bounds',None,['price_out_of_bounds']),
        ('above','110.000000000000000001','invalid_input','price_out_of_bounds',None,['price_out_of_bounds'])]:
        s,rq=base(S='110');s['model_facts']=[x for x in s['model_facts'] if x['kind']!='volatility']
        s['quotes']=[quote(target,target)];rq['output_ids']=['volatility.implied_volatility']
        dd=deps(s,DEFINITION+SPOT+FACTS+QUOTE)
        add('iv-bound-'+name,['iv_bounds','readiness','quotes'],s,rq,
            [expected(rq['output_ids'][0],value,dd,status,reason,flags)],'Exact original decimal bounds 10 and 110; no floating bound equality.')
    def inverse(s,rq,target):
        # Independent monotone root bisection at each precision, not production IV.
        roots=[]
        d=s['definitions'][0]; f={x['kind']:x['value'] for x in s['model_facts']}
        for ctx in contexts:
            S,K,r,q,T=[oracle.rational(ctx,x) for x in [s['spots'][0]['value'],d['strike'],rational_text(f['rate']),rational_text(f['carry']),rational_text(Fraction(d['fixing_ns']-NOW,YEAR_NS))]]
            p=oracle.rational(ctx,target);lo=ctx.mpf(0);hi=ctx.mpf(8)
            for _ in range(600):
                mid=(lo+hi)/2
                if mid==lo or mid==hi:break
                if oracle.price(ctx,d['right'],S,K,r,q,mid,T)<p:lo=mid
                else:hi=mid
            roots.append((lo+hi)/2)
        return roots
    for name,S,K,r,q,target,cap,iters,families in [
        ('ordinary','100','100',0.0,0.0,'10',8.0,256,['iv_bounds','readiness']),
        ('carry','103','97',0.03,0.01,'15',8.0,256,['iv_bounds','readiness']),
        ('tail','75','120',0.01,0.0,'0.00000000000000000001',8.0,256,['conditioning']),
        ('cap','100','100',0.0,0.0,'60',0.1,256,['iv_bounds']),
        ('iteration','100','100',0.0,0.0,'10',8.0,1,['iv_bounds'])]:
        s,rq=base(S=S,K=K,rate=r,carry=q);s['model_facts']=[x for x in s['model_facts'] if x['kind']!='volatility']
        s['quotes']=[quote(target,target)];rq['output_ids']=['volatility.implied_volatility'];rq['solver'].update(max_sigma=cap,max_iterations=iters,vol_abs_tol=1e-12,vol_rel_tol=1e-12)
        dd=deps(s,DEFINITION+SPOT+FACTS+QUOTE);k=rq['output_ids'][0]
        if name in ('cap','iteration'):
            status,reason=('bracket_exceeded','sigma_cap') if name=='cap' else ('iteration_limit','iteration_budget')
            wanted=expected(k,None,dd,status,reason,[reason])
        else:
            roots=inverse(s,rq,target)
            wanted=numeric_wanted(k,roots,dd)
            wanted['quality_flags']=iv_condition_flags(s,rq,roots)['quality_flags']
            wanted['solver_assertions']=dict(presence='required',converged=True,boundary='none')
        add('iv-'+name,families,s,rq,[wanted],'Independent original-decimal target and 80/140 digit monotone bisection; no production round trip.')
    for multiplier in ('10','100','150'):
        s,rq=base(multiplier=multiplier);rq['output_ids']=['contract.multiplier','contract.moneyness']
        add('reference-units-'+multiplier,['units'],s,rq,[expected('contract.multiplier',multiplier,deps(s,DEFINITION)),
            expected('contract.moneyness','1',deps(s,DEFINITION+SPOT))],'Direct original multiplier; K/S=1; no option-position scaling.')
    # DTE0 with positive exact-ns model time; exact integer subtraction.
    s,rq=base(years=Fraction(1,YEAR_NS));s['definitions'][0]['expiry_ordinal']=738000
    for cb in s['civil_bindings']:cb['ordinal']=738000
    rq['output_ids']=['contract.dte']
    dd=deps(s,DEFINITION+[('civil_bindings','civil_date_binding')])
    add('dte-zero-positive-nanosecond',['time'],s,rq,[expected('contract.dte','0',dd)],'Civil difference zero with fixing_ns-valuation_ns exactly one.')
    # Isolated semantic faults, no unrelated faulty inputs.
    for name,status,reason,change in [
        ('american','unsupported_profile','unsupported_exercise',('exercise','american')),
        ('discrete','unsupported_profile','unsupported_dividend_profile',('model_profile_admission','unsupported_discrete_dividends')),
        ('unknown','unsupported_profile','profile_uncertified',('model_profile_admission','unknown'))]:
        s,rq=base();s['definitions'][0][change[0]]=change[1];rq['output_ids']=['pricing.price']
        add('profile-'+name,['profile'],s,rq,[expected('pricing.price',None,deps(s,DEFINITION),status,reason,[reason])],
            'Known unsupported profile blocks model stage; no unrelated outputs requested.')
    for name,bid,ask,status,reason in [('locked','2','2','available','ok'),('crossed','3','2','invalid_input','crossed_quote'),
        ('negative','-1','2','invalid_input','negative_quote'),('one-sided',None,'2','ineligible_input','one_sided_quote'),
        ('zero','0','0','undefined','zero_midpoint'),('stale','1','2','ineligible_input','stale_quote'),('future','1','2','ineligible_input','future_known')]:
        s,rq=base();s['quotes']=[quote(bid,ask)];rq['output_ids']=['liquidity.spread_bps']
        if name=='stale':s['quotes'][0]['event_ns']=NOW-1001;s['quotes'][0]['known_at_ns']=NOW-1001
        if name=='future':s['quotes'][0]['known_at_ns']=NOW+1
        dd=deps(s,DEFINITION+QUOTE)
        add('quote-'+name,['quotes'],s,rq,[expected('liquidity.spread_bps','0' if name=='locked' else None,dd,status,reason,[] if reason=='ok' else [reason])],
            'Independent spread formula and isolated normative quote-eligibility fault.')
    # Independently supplied Greek remains ready without spot/model/quotes.
    s,rq=base();s['spots']=[];s['model_facts']=[]
    metric=dict(contract_id='OPT',output_id='greeks.signed_delta',value=-0.375,unit='signed_delta',
                producer_model_id='original-synthetic-producer',producer_formula_id='synthetic-delta1',event_ns=NOW,
                known_at_ns=NOW,revision_id='metric-1',input_binding_id='original-synthetic')
    s['supplied_metrics']=[metric];rq.update(output_ids=['greeks.delta'],origin_policy='supplied_only',supplied_delta_policy='absolute_from_signed')
    add('supplied-absolute-projection',['readiness','units','profile'],s,rq,[expected('greeks.delta','0.375',deps(s,DEFINITION+[('supplied_metrics','supplied_metric')]),
        producer=('original-synthetic-producer','synthetic-delta1'))],'Exact dyadic -3/8 supplied derivative projected to absolute delta with true producer preserved.')
    # Per-contract sample coverage, complete original synthetic ingestion.
    for complete in (True,False):
        s,rq=base();rq['output_ids']=['quality.quote_coverage'];s['quotes']=[quote('1','2')];s['quotes'][0].update(sample_id='slot-a',event_ns=NOW-1)
        window=dict(contract_id='OPT',known_at_ns=NOW,window_start_ns=NOW-10,window_end_ns=NOW,
                    expected_sample_ids=['slot-a','slot-b'],sampling_plan_id='original-plan',completeness_certificate_id='cert',input_binding_id='original-synthetic')
        cert=dict(certificate_id='cert',kind='quote_samples',contract_ids=['OPT'],window_start_ns=NOW-10,window_end_ns=NOW,
                  known_at_ns=NOW,complete=complete,input_binding_id='original-synthetic')
        s['quote_coverage_windows']=[window];s['coverage_certificates']=[cert]
        dd=deps(s,DEFINITION+QUOTE+[('quote_coverage_windows','quote_coverage_window'),('coverage_certificates','coverage_certificate')])
        wanted=expected('quality.quote_coverage','0.5' if complete else None,dd,'available' if complete else 'ineligible_input',
                        'ok' if complete else 'incomplete_source',['partial_quote_coverage'] if complete else ['incomplete_source'])
        add('coverage-'+str(complete).lower(),['quotes','readiness'],s,rq,[wanted],'Declared two-slot denominator, one eligible slot; incomplete certification never implies observed zero.')
    # Independent one-member breadth score, distinct from sample coverage.
    s,rq=base();rq['output_ids']=['chain.activity'];rq['contract_ids']=[]
    s['quotes']=[quote('1','2')]
    trade=dict(trade_id='trade-a',contract_id='OPT',quantity='1',quantity_unit='contracts',classification='regular',
               event_ns=NOW-1,known_at_ns=NOW,revision_id='trade-1',input_binding_id='original-synthetic')
    s['trades']=[trade]
    s['coverage_certificates']=[dict(certificate_id=identifier,kind=kind,contract_ids=['OPT'],
        window_start_ns=start,window_end_ns=end,known_at_ns=NOW,complete=True,input_binding_id='original-synthetic')
        for identifier,kind,start,end in [('trade-cert','trade_events',NOW-10,NOW),('quote-cert','current_quotes',NOW,NOW)]]
    activity=dict(population_id='original-one-member',underlying_id='UND',expected_contract_ids=['OPT'],known_at_ns=NOW,
        window_start_ns=NOW-10,window_end_ns=NOW,trade_ids=['trade-a'],trade_rule_id='synthetic-regular1',
        trade_completeness_certificate_id='trade-cert',quote_completeness_certificate_id='quote-cert',input_binding_id='original-synthetic')
    s['activity_window']=activity
    dd=deps(s,DEFINITION+QUOTE+[('trades','trade'),('coverage_certificates','coverage_certificate')])+[('activity_window',activity)]
    add('activity-one-of-one',['quotes','readiness'],s,rq,[expected('chain.activity','100',dd)],
        'Original breadth100*A/N: independently declared one member, positive eligible trade and current eligible quote, complete synthetic populations.')
    for name in ('missing-civil','contradictory-civil'):
        s,rq=base();rq['output_ids']=['contract.dte']
        if name=='missing-civil':s['civil_bindings']=[]
        else:s['civil_bindings'][0]['ordinal']=738001
        status,reason=('missing_input','missing_civil_binding') if name=='missing-civil' else ('invalid_input','civil_binding_mismatch')
        add(name,['time'],s,rq,[expected('contract.dte',None,deps(s,DEFINITION+[('civil_bindings','civil_date_binding')]),status,reason,[reason])],
            'UTC clock remains intact; only the independently supplied civil certification is absent or contradictory.')
    s,rq=base(years=-1);s['spots']=[];s['model_facts']=[];rq['output_ids']=['pricing.price']
    add('expired-without-model-facts',['time','readiness'],s,rq,[expected('pricing.price',None,deps(s,DEFINITION),'not_applicable','expired',['expired'])],
        'Exact negative remaining_ns establishes expiry before unrelated absent pricing operands.')
    s,rq=base(years=0);s['spots']=[];s['model_facts']=[];rq['output_ids']=['volatility.implied_volatility']
    add('terminal-iv-without-pricing-facts',['terminal','readiness'],s,rq,[expected('volatility.implied_volatility',None,deps(s,DEFINITION),
        'nonidentifiable_inverse','terminal_price',['terminal_price'])],'Terminal inverse nonidentifiable without demanding any quote/model/spot operand.')
    # General endpoint mathematics, including nonzero time slopes. Exact H=0
    # is established by S=K,r=q, never by rounded numerical cancellation.
    def general_endpoint(ctx,right,Stext,Ktext,rate,carry,sigma,T):
        S,K,r,q,v,t=[oracle.rational(ctx,x) for x in (Stext,Ktext,rational_text(rate),rational_text(carry),rational_text(sigma),str(T))]
        eta=1 if right=='call' else -1
        A,B=S*ctx.exp(-q*t),K*ctx.exp(-r*t)
        h=S-K if T==0 else A-B
        equal=(Stext==Ktext and (T==0 or rate==carry))
        if equal:h=ctx.mpf(0)
        itm=eta*h>0
        values={k:ctx.mpf(0) for k in MODEL_OUTPUTS};statuses={}
        values['pricing.price']=max(eta*h,ctx.mpf(0))
        if not equal:
            values['greeks.signed_delta']=eta*(ctx.mpf(1) if T==0 else ctx.exp(-q*t)) if itm else ctx.mpf(0)
            values['greeks.delta']=abs(values['greeks.signed_delta'])
            values['greeks.rho']=eta*t*B if itm and T else ctx.mpf(0)
            values['greeks.theta']=eta*(q*A-r*B) if itm else ctx.mpf(0)
        else:
            reason='nondifferentiable_payoff' if T==0 else 'nondifferentiable_zero_volatility'
            for k in ('greeks.signed_delta','greeks.delta','greeks.gamma'):
                values.pop(k);statuses[k]=('undefined',reason)
            if T:
                values.pop('greeks.rho');statuses['greeks.rho']=('undefined',reason)
                values['greeks.vega']=A*ctx.sqrt(t)/ctx.sqrt(2*ctx.pi)
                # With r=q and S=K, this directional time slope is exact zero.
                values['greeks.theta']=ctx.mpf(0)
            elif sigma:
                values.pop('greeks.theta');statuses['greeks.theta']=('undefined','nonfinite_terminal_time_derivative')
            else:
                values['greeks.theta']=-max(eta*(r-q)*S,ctx.mpf(0))
        return values,statuses
    for right in ('call','put'):
        for name,S,rate,carry,sigma,T in [
            ('terminal-itm-slope','110' if right=='call' else '90',0.03,0.01,0.25,0),
            ('terminal-otm-no-slope','90' if right=='call' else '110',0.03,0.01,0.25,0),
            ('terminal-kink-directional','100',0.03,0.01,0.0,0),
            ('zero-vol-positive-H','110',0.03,0.01,0.0,1),
            ('zero-vol-negative-H','90',0.03,0.01,0.0,1),
            ('zero-vol-exact-H','100',0.03,0.03,0.0,1)]:
            s,rq=base(right,S,rate=rate,carry=carry,sigma=sigma,years=T)
            vv=[general_endpoint(ctx,right,S,'100',rate,carry,sigma,T) for ctx in contexts]
            if vv[0][1]!=vv[1][1]:raise ArithmeticError('endpoint status disagreement')
            wanted=[]
            for k in rq['output_ids']:
                dd=deps(s,DEFINITION+SPOT+FACTS) if T else deps(s,DEFINITION+SPOT)
                if not T:
                    if k in ('greeks.vega','greeks.rho'):dd=deps(s,DEFINITION)
                    if k=='greeks.theta':
                        itm=(1 if right=='call' else -1)*(Decimal(S)-100)>0
                        kinds={'rate','carry'} if itm else set()
                        if S=='100':kinds={'volatility','rate','carry'}
                        dd += [('model_fact',row) for row in s['model_facts'] if row['kind'] in kinds]
                if k in vv[0][1]:
                    st,reason=vv[0][1][k];wanted.append(expected(k,None,dd,st,reason,[reason]))
                else:wanted.append(numeric_wanted(k,[v[0][k] for v in vv],dd))
            add(name+'-'+right,['terminal' if T==0 else 'zero_volatility','units'],s,rq,wanted,
                'Independent exact endpoint reduction with nonzero binary64 r/q; no small-time/sigma approximation.')
    for name,field,value,reason in [
        ('bermudan','exercise','bermudan','unsupported_exercise'),
        ('adjusted','deliverable','adjusted','unsupported_deliverable'),
        ('basket','deliverable','basket','unsupported_deliverable'),
        ('stochastic','model_profile_admission','unsupported_stochastic_or_local','unsupported_volatility_profile'),
        ('other','model_profile_admission','unsupported_other','unsupported_model_profile'),
        ('payment-lag','payment_ns',NOW+YEAR_NS+1,'unsupported_payment_lag')]:
        s,rq=base();s['definitions'][0][field]=value;rq['output_ids']=['pricing.price']
        add('profile-'+name,['profile'],s,rq,[expected('pricing.price',None,deps(s,DEFINITION),'unsupported_profile',reason,[reason])],
            'Isolated known unsupported model attribute, no guessed model eligibility.')
    for name in ('stale-spot','future-spot-event','future-spot-known','future-rate','inactive-rate'):
        s,rq=base();rq['output_ids']=['pricing.price'];dd=deps(s,DEFINITION+SPOT+FACTS)
        reason={'stale-spot':'stale_spot','future-spot-event':'future_event','future-spot-known':'future_known','future-rate':'future_known','inactive-rate':'inactive_interval'}[name]
        if name=='stale-spot':s['spots'][0].update(event_ns=NOW-1001,known_at_ns=NOW-1001)
        elif name=='future-spot-event':s['spots'][0]['event_ns']=NOW+1
        elif name=='future-spot-known':s['spots'][0]['known_at_ns']=NOW+1
        else:
            row=next(x for x in s['model_facts'] if x['kind']=='rate')
            row['known_at_ns' if name=='future-rate' else 'effective_from_ns']=NOW+1
        dd=deps(s,DEFINITION+SPOT+FACTS)
        add('readiness-'+name,['readiness'],s,rq,[expected('pricing.price',None,dd,'ineligible_input',reason,[reason])],
            'No causal alternative for isolated future/stale/inactive required fact; excluded record preserves failure provenance.')
    # A future-known specific volatility does not suppress a causal flat fact.
    s,rq=base();rq['output_ids']=['pricing.price']
    flat=next(x for x in s['model_facts'] if x['kind']=='volatility');flat['contract_id']=None
    future=dict(flat,contract_id='OPT',known_at_ns=NOW+1,revision_id='future-specific',value=0.5)
    s['model_facts'].append(future)
    causal=dict(s,model_facts=[x for x in s['model_facts'] if x is not future])
    vals=two_values(causal)
    add('causal-flat-survives-future-specific',['readiness'],s,rq,[numeric_wanted('pricing.price',[x['pricing.price'] for x in vals],deps(causal,DEFINITION+SPOT+FACTS))],
        'Causal flat volatility selected; excluded future-specific row changes snapshot identity but no selected mathematical dependency.')
    for name,change,status,reason in [
        ('future-event',{'event_ns':NOW+1},'ineligible_input','future_event'),
        ('one-sided-iv',{'bid':None},'ineligible_input','one_sided_quote'),
        ('zero-mid-iv',{'bid':'0','ask':'0'},'undefined','zero_midpoint')]:
        s,rq=base();s['model_facts']=[x for x in s['model_facts'] if x['kind']!='volatility']
        s['quotes']=[quote('9','11')];s['quotes'][0].update(change);rq['output_ids']=['volatility.implied_volatility']
        add('quote-'+name,['quotes'],s,rq,[expected(rq['output_ids'][0],None,deps(s,DEFINITION+SPOT+FACTS+QUOTE),status,reason,[reason])],
            'Isolated IV quote eligibility; malformed bounds are not inferred from an ineligible quote.')
    # Independent exact Decimal bounds that collapse to identical binary64.
    big='1'+'0'*100;lower='9'*100
    if float(big)!=float(lower):raise ArithmeticError('collapsed-bound construction failed')
    for label,target,status,reason,value,flags in [('lower',lower,'available','ok','0',['lower_boundary']),
        ('upper',big,'nonidentifiable_inverse','upper_asymptote',None,['upper_asymptote'])]:
        s,rq=base(S=big,K='1');s['model_facts']=[x for x in s['model_facts'] if x['kind']!='volatility']
        s['quotes']=[quote(target,target)];rq['output_ids']=['volatility.implied_volatility']
        add('collapsed-preview-'+label,['iv_bounds','conditioning'],s,rq,[expected(rq['output_ids'][0],value,deps(s,DEFINITION+SPOT+FACTS+QUOTE),status,reason,flags)],
            'Exact L=10^100-1 and U=10^100 are distinct despite identical binary64 previews; original Decimal endpoint identity decides.')
    # Quantize independently evaluated transcendental bounds to 18 fractional
    # digits; adjacent decimal quotes round to one binary64 value on both sides.
    for bound in ('lower','upper'):
        s0,rq0=base(S='110',rate=0.03,carry=0.01)
        values=[]
        for ctx in contexts:
            A=ctx.mpf(110)*ctx.exp(-oracle.rational(ctx,rational_text(0.01)))
            B=ctx.mpf(100)*ctx.exp(-oracle.rational(ctx,rational_text(0.03)))
            values.append(A-B if bound=='lower' else A)
        lo_bridge=high.mpf(contexts[0].nstr(values[0],82))
        oracle.agree(high,lo_bridge,values[1],'1e-60','0','transcendental bound')
        integer=int(high.floor(values[1]*10**18))
        for side,n in [('below',integer),('above',integer+1)]:
            target=str(n//10**18)+'.'+str(n%10**18).rjust(18,'0')
            exact=high.mpf(target)
            if (side=='below')!=(exact<values[1]):raise ArithmeticError('bound side not established')
            if abs(exact-values[1])<=abs(values[1])*high.mpf('1e-60'):raise ArithmeticError('insufficient oracle side margin')
            if float(target)!=float(values[1]):raise ArithmeticError('bound preview does not coincide')
            s,rq=base(S='110',rate=0.03,carry=0.01);s['model_facts']=[x for x in s['model_facts'] if x['kind']!='volatility']
            s['quotes']=[quote(target,target)];rq['output_ids']=['volatility.implied_volatility'];rq['solver'].update(vol_abs_tol=1e-12,vol_rel_tol=1e-12)
            k=rq['output_ids'][0];dd=deps(s,DEFINITION+SPOT+FACTS+QUOTE)
            if (bound=='lower' and side=='below') or (bound=='upper' and side=='above'):
                wanted=expected(k,None,dd,'invalid_input','price_out_of_bounds',['price_out_of_bounds'])
            elif bound=='upper':wanted=expected(k,None,dd,'bracket_exceeded','sigma_cap',['sigma_cap'])
            else:
                roots=inverse(s,rq,target)
                wanted=numeric_wanted(k,roots,dd)
                wanted['quality_flags']=iv_condition_flags(s,rq,roots)['quality_flags']
                wanted['solver_assertions']=dict(presence='required',converged=True,boundary='none')
            add('transcendental-'+bound+'-'+side,['iv_bounds','conditioning'],s,rq,[wanted],
                'Independent 80/140-digit bound and original decimal target have strict empirical side margin, yet binary64 previews coincide; no rounded endpoint clamp.')
    # Normative method range guards have explicit precision_exhausted outcomes.
    for name,S,K,rate,carry,sigma in [('rate-time-range','100','100',513.0,0.0,0.25),
        ('carry-time-range','100','100',0.0,-513.0,0.25),('sigma-range','100','100',0.0,0.0,4097.0),
        ('d1-range','0.00000000000000000001','100',0.0,0.0,1e-6),
        ('destructive-tail','1','100',0.0,0.0,0.01)]:
        s,rq=base(S=S,K=K,rate=rate,carry=carry,sigma=sigma);rq['output_ids']=['pricing.price']
        wanted=expected('pricing.price',None,deps(s,DEFINITION+SPOT+FACTS),'numerical_failure','precision_exhausted',['precision_exhausted'])
        if name=='destructive-tail':
            for ctx in contexts:
                p=oracle.price(ctx,'call',ctx.mpf(1),ctx.mpf(100),ctx.mpf(0),ctx.mpf(0),oracle.rational(ctx,rational_text(sigma)),ctx.mpf(1))
                if p<=0 or ctx.log10(p)>-10000:raise ArithmeticError('destructive tail witness failed')
        add('method-'+name,['conditioning'],s,rq,[wanted],
            'Explicit NUMERICAL_METHOD range guard, or deep nonzero erfc tail below binary64 and certificate-grid representability; no invented economic invalidity.')
    # A generic decimal target has a non-dyadic inverse. Subnormal positive
    # tolerances cannot admit an adjacent-binary64 bracket; no exact endpoint.
    s,rq=base();s['model_facts']=[x for x in s['model_facts'] if x['kind']!='volatility'];s['quotes']=[quote('10','10')]
    rq['output_ids']=['volatility.implied_volatility'];rq['solver'].update(max_iterations=4096,price_abs_tol=5e-324,price_rel_tol=5e-324,vol_abs_tol=5e-324,vol_rel_tol=5e-324)
    roots=inverse(s,rq,'10');nearest=float(roots[-1])
    # Independent price separation at nearest binary64 witnesses that nearest
    # representable sigma is not an exact root; review the method inference.
    for ctx in contexts:
        p=oracle.price(ctx,'call',ctx.mpf(100),ctx.mpf(100),ctx.mpf(0),ctx.mpf(0),oracle.rational(ctx,rational_text(nearest)),ctx.mpf(1))
        if abs(p-10)<ctx.mpf('1e-30'):raise ArithmeticError('stagnation witness too weak')
    add('method-representable-stagnation',['iv_bounds','conditioning'],s,rq,[expected('volatility.implied_volatility',None,deps(s,DEFINITION+SPOT+FACTS+QUOTE),
        'numerical_failure','precision_exhausted',['precision_exhausted'])],
        'Method expectation from subnormal tolerances, independent non-root witness at nearest binary64, and required strict interior progress; instrumentation audit still required.')
    # More source-completeness semantics: known empty/zero differs from unknown.
    for name in ('zero-observed','empty-plan','missing-certificate','future-plan'):
        s,rq=base();rq['output_ids']=['quality.quote_coverage']
        s['quote_coverage_windows']=[dict(contract_id='OPT',known_at_ns=NOW,window_start_ns=NOW-10,window_end_ns=NOW,
            expected_sample_ids=[] if name=='empty-plan' else ['slot-a'],sampling_plan_id='original-plan',completeness_certificate_id='cert',input_binding_id='original-synthetic')]
        s['coverage_certificates']=[] if name=='missing-certificate' else [dict(certificate_id='cert',kind='quote_samples',contract_ids=['OPT'],
            window_start_ns=NOW-10,window_end_ns=NOW,known_at_ns=NOW,complete=True,input_binding_id='original-synthetic')]
        if name=='future-plan':s['quote_coverage_windows'][0]['known_at_ns']=NOW+1
        status,reason,value,flags={'zero-observed':('available','ok','0',['partial_quote_coverage']),
            'empty-plan':('undefined','empty_sampling_plan',None,['empty_sampling_plan']),
            'missing-certificate':('ineligible_input','completeness_unknown',None,['completeness_unknown']),
            'future-plan':('ineligible_input','future_known',None,['future_known'])}[name]
        dd=deps(s,DEFINITION+[('quote_coverage_windows','quote_coverage_window'),('coverage_certificates','coverage_certificate')])
        add('coverage-'+name,['quotes','readiness'],s,rq,[expected('quality.quote_coverage',value,dd,status,reason,flags)],
            'Declared sample denominator and causal original certification; observed zero requires known complete nonempty population.')
    # Reuse the independently constructed one-member activity inputs, never an
    # actual production output. Derive changed population outcomes explicitly.
    original_activity=next(c for c in cases if c['id']=='activity-one-of-one')
    for name in ('zero','empty','incomplete','cancelled-revision','end-exclusive'):
        s=json.loads(json.dumps(original_activity['snapshot_payload']));rq=json.loads(json.dumps(original_activity['request_payload']))
        if name=='zero':s['trades']=[];s['activity_window']['trade_ids']=[]
        elif name=='empty':
            s['trades']=[];s['activity_window'].update(expected_contract_ids=[],trade_ids=[])
            for cert in s['coverage_certificates']:cert['contract_ids']=[]
        elif name=='incomplete':s['coverage_certificates'][0]['complete']=False
        elif name=='end-exclusive':s['trades'][0]['event_ns']=NOW
        else:
            s['trades'][0]['known_at_ns']=NOW-1
            cancelled=dict(s['trades'][0],classification='cancelled',known_at_ns=NOW,revision_id='trade-2')
            s['trades'].append(cancelled)
        status,reason,value,flags=('undefined','empty_population',None,['empty_population']) if name=='empty' else (
            ('ineligible_input','incomplete_source',None,['incomplete_source']) if name=='incomplete' else ('available','ok','0',['zero_activity']))
        dd=deps(s,DEFINITION+QUOTE+[('trades','trade'),('coverage_certificates','coverage_certificate')])+[('activity_window',s['activity_window'])]
        if name=='cancelled-revision':dd=[(kind,row) for kind,row in dd if not(kind=='trade' and row['revision_id']=='trade-1')]
        add('activity-'+name,['readiness','quotes'],s,rq,[expected('chain.activity',value,dd,status,reason,flags)],
            'Original breadth formula with independently changed complete population/event eligibility, including cancellation winner and half-open end.')
    # Source-stage precedence fixes dependency selection before any runtime.
    # Do not traverse quotes/events beyond failed completeness admission or
    # consume a certificate behind a future-known sampling plan.
    for case in cases:
        snapshot=case['snapshot_payload'];identifier=case['id']
        for wanted in case['expected']:
            corrected=None
            if identifier=='coverage-false':
                corrected=deps(snapshot,DEFINITION+[('quote_coverage_windows','quote_coverage_window'),('coverage_certificates','coverage_certificate')])
            elif identifier=='coverage-future-plan':
                corrected=deps(snapshot,DEFINITION+[('quote_coverage_windows','quote_coverage_window')])
            elif identifier=='activity-empty':
                corrected=deps(snapshot,[('coverage_certificates','coverage_certificate')])+[('activity_window',snapshot['activity_window'])]
            elif identifier=='activity-incomplete':
                corrected=deps(snapshot,DEFINITION+[('coverage_certificates','coverage_certificate')])+[('activity_window',snapshot['activity_window'])]
            if corrected is not None:
                wanted['dependency_binding_ids']=sorted({row['input_binding_id'] for _,row in corrected})
                wanted['dependency_record_sha256s']=sorted({record_digest(kind,row) for kind,row in corrected})
            if identifier in ('coverage-true','coverage-zero-observed','coverage-empty-plan'):
                window=snapshot['quote_coverage_windows'][0]
                wanted['coverage']=dict(observed=1 if identifier=='coverage-true' else 0,
                    expected=len(window['expected_sample_ids']),population_id=window['sampling_plan_id'],population_complete=True,sampling='event_count')
            elif identifier.startswith('activity-') and identifier!='activity-incomplete':
                window=snapshot['activity_window']
                wanted['coverage']=dict(observed=1 if identifier=='activity-one-of-one' else 0,
                    expected=len(window['expected_contract_ids']),population_id=window['population_id'],population_complete=True,sampling='population_member')
            if wanted['output_id']!='volatility.implied_volatility':continue
            reason=wanted['reason']
            if wanted['status']=='available' and wanted['oracle_decimal']=='0':
                # Exact boundary conditioning policy is recorded independently;
                # this follows the same frozen Vega inequality, not a tail-only special case.
                wanted['quality_flags']=iv_condition_flags(case['snapshot_payload'],case['request_payload'],[ctx.mpf(0) for ctx in contexts],wanted['quality_flags'])['quality_flags']
                wanted['solver_assertions']=dict(presence='required',converged=True,boundary='lower_boundary',iterations=0)
            elif wanted['status']=='available':
                wanted['solver_assertions']=dict(presence='required',converged=True,boundary='none')
            elif reason=='terminal_price' or reason in ('one_sided_quote','zero_midpoint','future_event','future_known','stale_quote'):
                wanted['solver_assertions']=dict(presence='absent')
            elif reason=='sigma_cap':
                wanted['solver_assertions']=dict(presence='required',converged=False,boundary='sigma_cap',iterations=0)
            elif reason=='iteration_budget':
                wanted['solver_assertions']=dict(presence='required',converged=False,boundary='none',iterations=case['request_payload']['solver']['max_iterations'])
            elif reason=='upper_asymptote':
                wanted['solver_assertions']=dict(presence='not_fixed_by_contract',if_present=dict(converged=False,boundary='upper_asymptote',iterations=0))
            elif reason=='price_out_of_bounds':
                wanted['solver_assertions']=dict(presence='not_fixed_by_contract',if_present=dict(converged=False,iterations=0))
            elif reason=='precision_exhausted':
                wanted['solver_assertions']=dict(presence='required',converged=False,boundary='none')
            assertions=wanted['solver_assertions']
            if assertions['presence']!='absent':
                quotes=case['snapshot_payload']['quotes']
                if quotes and quotes[0]['bid'] is not None and quotes[0]['ask'] is not None:
                    # All admitted inverse fixtures use locked original Decimal
                    # targets. No ambient Decimal-context arithmetic is needed.
                    if quotes[0]['bid']!=quotes[0]['ask']:raise ArithmeticError('fixture target requires exact midpoint extension')
                    assertions['target_price_exact']=quotes[0]['bid']
            if wanted['status']=='available':
                roots=[ctx.mpf(wanted['oracle_decimal']) for ctx in contexts]
                assessment=iv_condition_flags(case['snapshot_payload'],case['request_payload'],roots,wanted['quality_flags'])
                assertions.update(ill_conditioned=assessment['ill_conditioned'],oracle_vega=assessment['oracle_vega'],
                    require_sigma_contains_oracle=True,require_both_convergence_criteria=True)
    return cases


def exception_cases():
    """Schema failures are separate from valid records with unavailable outputs.

    Unless the frozen prose explicitly fixes a reason, assert the exception
    class only rather than inventing a package error-code mapping.
    """
    result=[]
    for name in ('unknown-field','bool-clock','duplicate-request-contract','fractional-contract-trade','negative-contract-trade'):
        snapshot,request=base()
        reason=None
        if name=='unknown-field':snapshot['unrecognized']=True
        elif name=='bool-clock':request['valuation_ns']=True
        elif name=='duplicate-request-contract':request['contract_ids']=['OPT','OPT']
        else:
            snapshot['trades']=[dict(trade_id='invalid-trade',contract_id='OPT',quantity='1.5' if name.startswith('fractional') else '-1',
                quantity_unit='contracts',classification='regular',event_ns=NOW,known_at_ns=NOW,revision_id='trade-1',input_binding_id='original-synthetic')]
            reason='out_of_range'
        result.append(dict(id='boundary-'+name,snapshot_payload=snapshot,request_payload=request,
            expected_exception='ContractValidationError',expected_reason=reason,
            reason_assertion='class_only' if reason is None else 'exact_reason',
            derivation='Explicit frozen schema rejection; no numerical evaluation or output-result surrogate.'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--review-receipt',type=Path)
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',args.source_commit):parser.error('exact lowercase 40-hex source commit required')
    if 'mpmath' in sys.modules:raise RuntimeError('fresh interpreter required')
    os.environ['MPMATH_NOGMPY']='1';os.environ['MPMATH_NOSAGE']='1';os.environ.pop('MPMATH_SAGE',None)
    if importlib.metadata.version('mpmath')!='1.3.0':raise RuntimeError('exact mpmath==1.3.0 required')
    import mpmath
    from mpmath.libmp.backend import BACKEND
    if BACKEND!='python':raise RuntimeError('pure Python oracle backend required')
    original=Path(__file__).with_name('generate_r25_oracle.py')
    spec=importlib.util.spec_from_file_location('original_r25_independent_oracle',original)
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    contexts=[mpmath.mp.clone() for _ in PRECISIONS]
    for ctx,digits in zip(contexts,PRECISIONS):ctx.dps=digits
    cases=artifact_cases(contexts,oracle)
    source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    exceptions=exception_cases()
    cases_sha=hashlib.sha256(canonical(dict(cases=cases,exception_cases=exceptions))).hexdigest()
    artifact=dict(schema_version='r25-independent-wire-fixtures1',state='wire_fixture_candidate_not_reviewed',
                  author=AUTHOR,reviewer=None,production_imports=False,dependency='mpmath==1.3.0',
                  precision_decimal_digits=list(PRECISIONS),generator_source_sha256=source_sha,
                  reviewed_source_commit=args.source_commit,original_oracle_source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                  cases_sha256=cases_sha,cases=cases,exception_cases=exceptions,omissions=OMISSIONS,python=sys.version,platform=platform.platform(),
                  oracle_uncertainty_kind='empirical_precision_agreement_not_rigorous_enclosure',
                  review_note='External receipt is an operator trust anchor, not cryptographic proof of reviewer identity.')
    if args.review_receipt:
        receipt=json.loads(args.review_receipt.read_text(encoding='utf-8'))
        for field,value in [('generator_source_sha256',source_sha),('reviewed_source_commit',args.source_commit),('cases_sha256',cases_sha)]:
            if receipt[field]!=value:raise ValueError('external review receipt mismatch: '+field)
        if receipt['reviewer'] in (AUTHOR,'/root/r25_library_implementation') or not receipt['reviewer']:raise ValueError('fresh independent reviewer required')
        if receipt['decision']!='approved_candidate_cases':raise ValueError('external candidate review approval required')
        artifact.update(state='independently_reviewed_wire_fixture_candidate',reviewer=receipt['reviewer'],
                        external_review_receipt_sha256=hashlib.sha256(args.review_receipt.read_bytes()).hexdigest())
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(artifact,stream,ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2);stream.write('\n')

if __name__=='__main__':main()

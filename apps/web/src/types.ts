export type FixtureId = 'credits'|'fulfillment'|'subscriptions';
export type State = Record<string, number|{status:string;version:number}>;
export interface Step {kind:'delivery'|'restart';sequence:number;event_id?:string;entity_id?:string;event_type?:string;payload?:Record<string,unknown>;arrival_time?:string}
export interface Contract {id:string;version:string;fixture_id:FixtureId;approved:boolean;semantics:string;deduplication_key:string;acknowledgement_status:number;rules:string[]}
export interface Incident {schema_version:string;incident_id:string;symptom:string;fixture_id:FixtureId;revision:string;initial_state:State;initial_state_hash:string;steps:Step[];contract:Contract;provenance:string;redacted:boolean;runtime_build:string}
export interface Fixture {id:FixtureId;title:string;symptom:string;expected:string;unit:string;incident:Incident}
export interface Progress {id:number;created:string;state:string;message:string}
export interface Replay {scenario_id:string;steps:{sequence:number;kind:string;event_id?:string;entity_id?:string;status?:number;state:State}[];infrastructure_error:string|null;check:{passed:boolean;inconclusive:boolean;failures:unknown[]}}
export interface TestResult {collected:number;passed:number;failures:number;errors:number;exit_status:number|null;output:string;meaningful_failure:boolean}
export interface Result {mode:string;verdict:string;explanation:string;diagnosis?:string;patch_explanation?:string;diff:string;original_source:string;candidate_source:string;test_source:string;scenarios:{id:string;name:string;steps:Step[];held_back:boolean}[];original_results:Replay[];candidate_results:Replay[];regression:{original?:TestResult;candidate?:TestResult};limitations:string[];counterexample?:{original_length:number;length:number;locally_minimal:boolean};artifacts?:{name:string;size:number}[];manifest:{elapsed_seconds?:number;execution_provider?:string;model_ids?:string[];sandbox_operation_ids?:string[];model_calls?:{usage?:{total_tokens?:number};estimated_cost_usd?:number|null}[];[key:string]:unknown}}
export interface Run {id:string;incident_id:string;mode:'reference'|'live'|'flawed';state:string;created:string;updated:string;result:Result|null}
export interface Health {ready:boolean;live_configured:boolean;model:string|null;execution_provider:string;public_demo:boolean}
export interface RecordingSummary {id:string;fixture_id:FixtureId;title:string;mode:Run['mode'];created:string;verdict:string;model_ids:string[]}
export interface Recording {recorded:true;incident:Incident;run:Run;events:Progress[]}

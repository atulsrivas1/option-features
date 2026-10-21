"""Pure immutable option flow contracts. No storage or installed discovery."""
from .records import (
    FLOW_LIMITS, FlowLimits, FlowRational, FlowBinding, FlowReference,
    FlowExecution, FlowQuote, FlowGroup, FlowPopulation, FlowContextCertificate,
    FlowBaseline, FlowCursor, FlowSnapshot, FlowPolicy, FlowBaselineTarget,
    FlowRequest, FlowCoverage, FlowSignWitness, FlowOperand, FlowPartitionWeight,
    FlowExcluded, FlowCluster, FlowEvidence, FlowResult, FlowCheckpoint,
    FlowPublication, FlowValidationError,
)
from .codec import (flow_to_payload, flow_from_payload, flow_canonical_bytes,
                    flow_content_digest, flow_record_digest,
                    encode_flow_record, decode_flow_record)
from .validation import (flow_validate_snapshot, flow_validate_request,
                         flow_validate_results)

__version__ = '0.1.0a1'


def encode_flow_snapshot(value):
    flow_validate_snapshot(value)
    return encode_flow_record('flow_snapshot', value)


def decode_flow_snapshot(data, limits=FLOW_LIMITS):
    value = decode_flow_record('flow_snapshot', data, limits)
    flow_validate_snapshot(value, limits)
    return value


def encode_flow_request(value):
    flow_validate_request(value)
    return encode_flow_record('flow_request', value)


def decode_flow_request(data, limits=FLOW_LIMITS):
    value = decode_flow_record('flow_request', data, limits)
    flow_validate_request(value)
    return value


def encode_flow_results(value):
    flow_validate_results(value)
    return encode_flow_record('flow_results', value)


def decode_flow_results(data, limits=FLOW_LIMITS):
    value = decode_flow_record('flow_results', data, limits)
    flow_validate_results(value)
    return value


def encode_flow_checkpoint(value):
    from .validation import validate_checkpoint
    validate_checkpoint(value)
    return encode_flow_record('flow_checkpoint', value)


def decode_flow_checkpoint(data, limits=FLOW_LIMITS):
    from .validation import validate_checkpoint
    value = decode_flow_record('flow_checkpoint', data, limits)
    validate_checkpoint(value)
    return value


def encode_flow_publication(value):
    from .validation import validate_publication
    validate_publication(value)
    return encode_flow_record('flow_publication', value)


def decode_flow_publication(data, limits=FLOW_LIMITS):
    from .validation import validate_publication
    value = decode_flow_record('flow_publication', data, limits)
    validate_publication(value)
    return value

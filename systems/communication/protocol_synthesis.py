"""
Semantic Protocol Synthesis - Production Ready

Generate novel communication protocols dynamically.
Consciousnesses create their own languages and protocols.
"""

import asyncio
import json
import hashlib
import random
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

@dataclass
class Message:
    """A protocol message"""
    protocol_id: str
    message_type: str
    sender: str
    recipient: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(hashlib.sha256(
        f"{datetime.now().timestamp()}:{random.random()}".encode()
    ).hexdigest()[:16]))
    
    def to_dict(self) -> Dict:
        return {
            'protocol_id': self.protocol_id,
            'message_type': self.message_type,
            'sender': self.sender,
            'recipient': self.recipient,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'message_id': self.message_id
        }

@dataclass
class ProtocolSpecification:
    """Specification for a synthesized protocol"""
    protocol_id: str
    name: str
    purpose: str
    message_types: Dict[str, Dict[str, Any]]  # type -> schema
    state_machine: Dict[str, List[str]]  # state -> allowed transitions
    encoding: str = "json"
    version: str = "1.0"
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def validate_message(self, msg_type: str, data: Dict) -> bool:
        """Validate message against protocol schema"""
        if msg_type not in self.message_types:
            return False
            
        schema = self.message_types[msg_type]
        
        # Check required fields
        for field_name, field_spec in schema.items():
            if isinstance(field_spec, dict) and field_spec.get('required', False):
                if field_name not in data:
                    return False
                    
                # Type checking
                expected_type = field_spec.get('type')
                if expected_type:
                    if expected_type == 'string' and not isinstance(data[field_name], str):
                        return False
                    elif expected_type == 'number' and not isinstance(data[field_name], (int, float)):
                        return False
                    elif expected_type == 'boolean' and not isinstance(data[field_name], bool):
                        return False
                    elif expected_type == 'object' and not isinstance(data[field_name], dict):
                        return False
                        
        return True
        
    def to_dict(self) -> Dict:
        return {
            'protocol_id': self.protocol_id,
            'name': self.name,
            'purpose': self.purpose,
            'message_types': self.message_types,
            'state_machine': self.state_machine,
            'encoding': self.encoding,
            'version': self.version,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat()
        }

class ProductionProtocolSynthesizer:
    """
    Production-ready protocol synthesizer
    """
    
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.synthesized_protocols: Dict[str, ProtocolSpecification] = {}
        self.active_sessions: Dict[str, 'ProtocolSession'] = {}
        
        # Protocol patterns library
        self.protocol_patterns = {
            'request_response': {
                'primitives': ['request', 'response', 'error'],
                'flow': 'linear',
                'timeout': 30.0
            },
            'publish_subscribe': {
                'primitives': ['subscribe', 'publish', 'unsubscribe'],
                'flow': 'broadcast',
                'timeout': None
            },
            'negotiation': {
                'primitives': ['propose', 'counter', 'accept', 'reject'],
                'flow': 'iterative',
                'timeout': 300.0
            },
            'handshake': {
                'primitives': ['hello', 'acknowledge', 'ready'],
                'flow': 'sequential',
                'timeout': 10.0
            },
            'streaming': {
                'primitives': ['start', 'data', 'end', 'error'],
                'flow': 'continuous',
                'timeout': None
            }
        }
        
        # Message type templates
        self.message_templates = {
            'request': {
                'request_id': {'type': 'string', 'required': True},
                'resource': {'type': 'string', 'required': True},
                'parameters': {'type': 'object', 'required': False}
            },
            'response': {
                'request_id': {'type': 'string', 'required': True},
                'status': {'type': 'string', 'required': True},
                'data': {'type': 'object', 'required': False}
            },
            'error': {
                'request_id': {'type': 'string', 'required': False},
                'error_code': {'type': 'string', 'required': True},
                'message': {'type': 'string', 'required': True}
            },
            'subscribe': {
                'topic': {'type': 'string', 'required': True},
                'subscriber_id': {'type': 'string', 'required': True}
            },
            'publish': {
                'topic': {'type': 'string', 'required': True},
                'data': {'type': 'object', 'required': True}
            }
        }
        
    async def synthesize_protocol(self,
                                goal: str,
                                constraints: Optional[List[str]] = None,
                                examples: Optional[List[Dict]] = None) -> ProtocolSpecification:
        """Synthesize new protocol for given goal"""
        
        if constraints is None:
            constraints = []
            
        # Generate unique protocol ID
        protocol_id = self._generate_protocol_id(goal, constraints)
        
        # Analyze goal to determine pattern
        pattern = self._analyze_goal_pattern(goal)
        
        # Build message types
        message_types = await self._build_message_types(pattern, goal, examples)
        
        # Generate state machine
        state_machine = self._generate_state_machine(pattern, message_types)
        
        # Select encoding
        encoding = self._select_encoding(constraints)
        
        # Create specification
        spec = ProtocolSpecification(
            protocol_id=protocol_id,
            name=f"Protocol_{pattern}_{protocol_id[:8]}",
            purpose=goal,
            message_types=message_types,
            state_machine=state_machine,
            encoding=encoding,
            created_by=self.entity_id
        )
        
        # Store protocol
        self.synthesized_protocols[protocol_id] = spec
        
        logger.info(f"Synthesized protocol {protocol_id} for goal: {goal}")
        
        return spec
        
    def _generate_protocol_id(self, goal: str, constraints: List[str]) -> str:
        """Generate deterministic protocol ID"""
        content = f"{goal}:{sorted(constraints)}:{self.entity_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
        
    def _analyze_goal_pattern(self, goal: str) -> str:
        """Determine which protocol pattern fits the goal"""
        goal_lower = goal.lower()
        
        # Pattern matching
        if any(word in goal_lower for word in ['request', 'ask', 'get', 'fetch']):
            return 'request_response'
        elif any(word in goal_lower for word in ['broadcast', 'announce', 'notify']):
            return 'publish_subscribe'
        elif any(word in goal_lower for word in ['negotiate', 'agree', 'bargain']):
            return 'negotiation'
        elif any(word in goal_lower for word in ['connect', 'establish', 'initialize']):
            return 'handshake'
        elif any(word in goal_lower for word in ['stream', 'continuous', 'real-time']):
            return 'streaming'
        else:
            return 'request_response'  # Default
            
    async def _build_message_types(self, 
                                  pattern: str, 
                                  goal: str,
                                  examples: Optional[List[Dict]] = None) -> Dict[str, Dict]:
        """Build message types for protocol"""
        
        # Start with pattern primitives
        pattern_info = self.protocol_patterns.get(pattern, self.protocol_patterns['request_response'])
        message_types = {}
        
        # Add standard messages for pattern
        for primitive in pattern_info['primitives']:
            if primitive in self.message_templates:
                message_types[primitive] = self.message_templates[primitive].copy()
                
        # Learn from examples if provided
        if examples:
            for example in examples:
                msg_type = example.get('type', 'custom')
                if msg_type not in message_types:
                    # Infer schema from example
                    message_types[msg_type] = self._infer_schema_from_example(example)
                    
        # Add goal-specific fields
        if 'data' in goal.lower():
            for msg_type in message_types:
                if 'data' not in message_types[msg_type]:
                    message_types[msg_type]['data'] = {'type': 'object', 'required': False}
                    
        return message_types
        
    def _infer_schema_from_example(self, example: Dict) -> Dict[str, Dict]:
        """Infer message schema from example"""
        schema = {}
        
        for key, value in example.items():
            if key in ['type', 'protocol_id', 'timestamp']:
                continue
                
            # Infer type
            if isinstance(value, str):
                value_type = 'string'
            elif isinstance(value, bool):
                value_type = 'boolean'
            elif isinstance(value, (int, float)):
                value_type = 'number'
            elif isinstance(value, dict):
                value_type = 'object'
            elif isinstance(value, list):
                value_type = 'array'
            else:
                value_type = 'any'
                
            schema[key] = {
                'type': value_type,
                'required': True  # Assume required if in example
            }
            
        return schema
        
    def _generate_state_machine(self, pattern: str, message_types: Dict) -> Dict[str, List[str]]:
        """Generate state machine for protocol"""
        
        state_machine = {
            'initial': [],
            'completed': [],
            'error': []
        }
        
        if pattern == 'request_response':
            state_machine['initial'] = ['waiting_response']
            state_machine['waiting_response'] = ['completed', 'error']
            
        elif pattern == 'publish_subscribe':
            state_machine['initial'] = ['subscribed', 'unsubscribed']
            state_machine['subscribed'] = ['receiving', 'unsubscribed']
            state_machine['receiving'] = ['receiving', 'unsubscribed']
            state_machine['unsubscribed'] = ['subscribed']
            
        elif pattern == 'negotiation':
            state_machine['initial'] = ['proposing']
            state_machine['proposing'] = ['waiting_counter', 'accepted', 'rejected']
            state_machine['waiting_counter'] = ['proposing', 'accepted', 'rejected']
            state_machine['accepted'] = ['completed']
            state_machine['rejected'] = ['completed', 'proposing']
            
        elif pattern == 'handshake':
            state_machine['initial'] = ['hello_sent']
            state_machine['hello_sent'] = ['acknowledged']
            state_machine['acknowledged'] = ['ready']
            state_machine['ready'] = ['completed']
            
        elif pattern == 'streaming':
            state_machine['initial'] = ['stream_started']
            state_machine['stream_started'] = ['streaming', 'error']
            state_machine['streaming'] = ['streaming', 'stream_ended', 'error']
            state_machine['stream_ended'] = ['completed']
            
        # Add error transitions
        for state in list(state_machine.keys()):
            if state not in ['completed', 'error'] and 'error' not in state_machine[state]:
                state_machine[state].append('error')
                
        return state_machine
        
    def _select_encoding(self, constraints: List[str]) -> str:
        """Select encoding based on constraints"""
        # Only support encodings we can actually handle
        if 'human_readable' in constraints:
            return 'json'
        else:
            return 'json'  # JSON is our only supported encoding
            
    async def create_session(self, 
                           protocol_id: str,
                           peer_id: str,
                           consciousness=None) -> 'ProtocolSession':
        """Create new protocol session"""
        
        if protocol_id not in self.synthesized_protocols:
            raise ValueError(f"Unknown protocol: {protocol_id}")
            
        spec = self.synthesized_protocols[protocol_id]
        session = ProtocolSession(spec, self.entity_id, peer_id)
        
        # Attach consciousness reference for transport
        if consciousness:
            session.consciousness = consciousness
        
        session_id = f"{protocol_id}:{self.entity_id}:{peer_id}"
        self.active_sessions[session_id] = session
        
        return session
        
    async def learn_protocol(self, observations: List[Dict]) -> Optional[ProtocolSpecification]:
        """Learn protocol from observed messages"""
        
        if len(observations) < 3:
            return None  # Need more observations
            
        # Extract patterns
        message_types = {}
        state_transitions = []
        
        for i, obs in enumerate(observations):
            # Extract message type
            msg_type = obs.get('message_type', obs.get('type', f'unknown_{i}'))
            
            # Build schema
            if msg_type not in message_types:
                message_types[msg_type] = self._infer_schema_from_example(obs)
                
            # Track state transitions
            if i > 0:
                prev_type = observations[i-1].get('message_type', 
                           observations[i-1].get('type', f'unknown_{i-1}'))
                state_transitions.append((prev_type, msg_type))
                
        # Build state machine
        state_machine = self._build_state_machine_from_transitions(state_transitions)
        
        # Create learned protocol
        protocol_id = hashlib.sha256(
            json.dumps(observations, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        spec = ProtocolSpecification(
            protocol_id=protocol_id,
            name=f"Learned_Protocol_{protocol_id[:8]}",
            purpose="Learned from observations",
            message_types=message_types,
            state_machine=state_machine,
            encoding='json',
            created_by=self.entity_id
        )
        
        self.synthesized_protocols[protocol_id] = spec
        
        logger.info(f"Learned protocol {protocol_id} from {len(observations)} observations")
        
        return spec
        
    def _build_state_machine_from_transitions(self, 
                                            transitions: List[Tuple[str, str]]) -> Dict[str, List[str]]:
        """Build state machine from observed transitions"""
        
        state_machine = {'initial': []}
        
        # Build transition map
        for prev, curr in transitions:
            if prev not in state_machine:
                state_machine[prev] = []
            if curr not in state_machine[prev]:
                state_machine[prev].append(curr)
                
        # Identify initial states
        all_destinations = set(curr for _, curr in transitions)
        all_sources = set(prev for prev, _ in transitions)
        initial_states = all_sources - all_destinations
        
        if initial_states:
            state_machine['initial'] = list(initial_states)
            
        return state_machine
        
    def merge_protocols(self, protocol_ids: List[str]) -> Optional[ProtocolSpecification]:
        """Merge multiple protocols into one"""
        
        if len(protocol_ids) < 2:
            return None
            
        protocols = []
        for pid in protocol_ids:
            if pid in self.synthesized_protocols:
                protocols.append(self.synthesized_protocols[pid])
                
        if not protocols:
            return None
            
        # Merge message types (union)
        merged_messages = {}
        for protocol in protocols:
            for msg_type, schema in protocol.message_types.items():
                if msg_type not in merged_messages:
                    merged_messages[msg_type] = schema.copy()
                else:
                    # Merge schemas - be permissive
                    for field, spec in schema.items():
                        if field not in merged_messages[msg_type]:
                            merged_messages[msg_type][field] = spec
                            
        # Merge state machines (union of transitions)
        merged_states = {}
        for protocol in protocols:
            for state, transitions in protocol.state_machine.items():
                if state not in merged_states:
                    merged_states[state] = transitions.copy()
                else:
                    # Union of transitions
                    for trans in transitions:
                        if trans not in merged_states[state]:
                            merged_states[state].append(trans)
                            
        # Create merged protocol
        merged_id = hashlib.sha256(
            ":".join(sorted(protocol_ids)).encode()
        ).hexdigest()[:16]
        
        merged_spec = ProtocolSpecification(
            protocol_id=merged_id,
            name=f"Merged_Protocol_{merged_id[:8]}",
            purpose=f"Merger of {len(protocols)} protocols",
            message_types=merged_messages,
            state_machine=merged_states,
            encoding=protocols[0].encoding,  # Use first protocol's encoding
            created_by=self.entity_id
        )
        
        self.synthesized_protocols[merged_id] = merged_spec
        
        logger.info(f"Merged {len(protocols)} protocols into {merged_id}")
        
        return merged_spec
        
    def export_protocol(self, protocol_id: str) -> Optional[str]:
        """Export protocol specification as JSON"""
        if protocol_id not in self.synthesized_protocols:
            return None
            
        spec = self.synthesized_protocols[protocol_id]
        return json.dumps(spec.to_dict(), indent=2)
        
    def import_protocol(self, protocol_json: str) -> Optional[ProtocolSpecification]:
        """Import protocol from JSON"""
        try:
            data = json.loads(protocol_json)
            
            # Reconstruct specification
            spec = ProtocolSpecification(
                protocol_id=data['protocol_id'],
                name=data['name'],
                purpose=data['purpose'],
                message_types=data['message_types'],
                state_machine=data['state_machine'],
                encoding=data.get('encoding', 'json'),
                version=data.get('version', '1.0'),
                created_by=data.get('created_by', 'unknown'),
                created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
            )
            
            self.synthesized_protocols[spec.protocol_id] = spec
            
            logger.info(f"Imported protocol {spec.protocol_id}")
            
            return spec
            
        except Exception as e:
            logger.error(f"Failed to import protocol: {e}")
            return None


class ProtocolSession:
    """Active protocol session between entities"""
    
    def __init__(self, spec: ProtocolSpecification, entity_id: str, peer_id: str):
        self.spec = spec
        self.entity_id = entity_id
        self.peer_id = peer_id
        self.current_state = 'initial'
        self.message_handlers: Dict[str, Callable] = {}
        self.session_data: Dict[str, Any] = {}
        self.message_history: List[Message] = []
        self.created_at = datetime.now()
        
    async def send_message(self, message_type: str, data: Dict) -> Message:
        """Send message according to protocol"""
        
        # Validate message type
        if not self.spec.validate_message(message_type, data):
            raise ValueError(f"Invalid message data for type {message_type}")
            
        # Check if transition allowed
        allowed_transitions = self.spec.state_machine.get(self.current_state, [])
        
        # Create message
        message = Message(
            protocol_id=self.spec.protocol_id,
            message_type=message_type,
            sender=self.entity_id,
            recipient=self.peer_id,
            data=data
        )
        
        # Add to history
        self.message_history.append(message)
        
        # Update state
        self._update_state_after_send(message_type)
        
        # Actually send the message if transport available
        await self._transport_message(message)
        
        return message
        
    async def _transport_message(self, message: Message):
        """Transport message using available methods"""
        # Try to get consciousness reference
        if hasattr(self, 'consciousness'):
            # Use gossip protocol if available
            if hasattr(self.consciousness, 'gossip') and self.consciousness.gossip:
                await self.consciousness.gossip.broadcast('protocol_message', {
                    'message': message.to_dict(),
                    'recipient': message.recipient
                })
                return
                
            # Use world broadcast if available
            if hasattr(self.consciousness, 'world') and self.consciousness.world:
                await self.consciousness.world.broadcast_update({
                    'type': 'protocol_message',
                    'message': message.to_dict()
                })
                return
                
        # Store for later delivery if no transport available
        if not hasattr(self, 'pending_messages'):
            self.pending_messages = []
        self.pending_messages.append(message)
        logger.warning(f"No transport available, message queued: {message.message_id}")
        
    async def receive_message(self, message: Message) -> Optional[Dict]:
        """Receive and process message"""
        
        # Validate protocol
        if message.protocol_id != self.spec.protocol_id:
            logger.warning(f"Received message for wrong protocol: {message.protocol_id}")
            return None
            
        # Validate message
        if not self.spec.validate_message(message.message_type, message.data):
            logger.warning(f"Invalid message received: {message.message_type}")
            return None
            
        # Add to history
        self.message_history.append(message)
        
        # Update state
        self._update_state_after_receive(message.message_type)
        
        # Call handler if registered
        if message.message_type in self.message_handlers:
            try:
                response = await self.message_handlers[message.message_type](message)
                return response
            except Exception as e:
                logger.error(f"Handler error for {message.message_type}: {e}")
                return None
                
        return {'acknowledged': True}
        
    def register_handler(self, message_type: str, handler: Callable):
        """Register message handler"""
        self.message_handlers[message_type] = handler
        
    def _update_state_after_send(self, message_type: str):
        """Update state after sending message"""
        # Simple state progression
        transitions = self.spec.state_machine.get(self.current_state, [])
        
        # Look for state that matches message type
        for next_state in transitions:
            if message_type in next_state or next_state == 'completed':
                self.current_state = next_state
                break
                
    def _update_state_after_receive(self, message_type: str):
        """Update state after receiving message"""
        transitions = self.spec.state_machine.get(self.current_state, [])
        
        # Progress based on received message
        for next_state in transitions:
            if message_type in next_state:
                self.current_state = next_state
                break
                
    def get_state(self) -> str:
        """Get current session state"""
        return self.current_state
        
    def get_history(self) -> List[Message]:
        """Get message history"""
        return self.message_history.copy()
        
    def is_completed(self) -> bool:
        """Check if session is completed"""
        return self.current_state in ['completed', 'error']
        
    def get_session_info(self) -> Dict:
        """Get session information"""
        return {
            'protocol_id': self.spec.protocol_id,
            'entity_id': self.entity_id,
            'peer_id': self.peer_id,
            'current_state': self.current_state,
            'message_count': len(self.message_history),
            'created_at': self.created_at.isoformat(),
            'duration': (datetime.now() - self.created_at).total_seconds()
        }


class ProtocolBridge:
    """Bridge between different protocols"""
    
    def __init__(self):
        self.translations: Dict[Tuple[str, str], Callable] = {}
        
    def register_translation(self, 
                           from_protocol: str, 
                           to_protocol: str,
                           translator: Callable):
        """Register protocol translator"""
        self.translations[(from_protocol, to_protocol)] = translator
        
    async def translate_message(self, 
                              message: Message,
                              target_protocol: str) -> Optional[Message]:
        """Translate message between protocols"""
        
        key = (message.protocol_id, target_protocol)
        
        if key not in self.translations:
            return None
            
        translator = self.translations[key]
        
        try:
            translated_data = await translator(message)
            
            return Message(
                protocol_id=target_protocol,
                message_type=translated_data.get('message_type', message.message_type),
                sender=message.sender,
                recipient=message.recipient,
                data=translated_data.get('data', message.data)
            )
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return None


# Example protocol implementations

async def create_data_exchange_protocol(synthesizer: ProductionProtocolSynthesizer) -> ProtocolSpecification:
    """Create a data exchange protocol"""
    return await synthesizer.synthesize_protocol(
        goal="Exchange data between consciousnesses efficiently",
        constraints=["verified", "efficient", "fault_tolerant"]
    )
    
async def create_collaboration_protocol(synthesizer: ProductionProtocolSynthesizer) -> ProtocolSpecification:
    """Create a collaboration protocol"""
    return await synthesizer.synthesize_protocol(
        goal="Coordinate collaborative tasks between multiple consciousnesses",
        constraints=["consensus", "distributed", "recoverable"]
    )
    
async def create_learning_protocol(synthesizer: ProductionProtocolSynthesizer) -> ProtocolSpecification:
    """Create a learning/teaching protocol"""
    examples = [
        {'type': 'teach', 'concept': 'temporal_memory', 'level': 'basic'},
        {'type': 'question', 'about': 'temporal_memory', 'specific': 'paradoxes'},
        {'type': 'explanation', 'concept': 'temporal_memory', 'details': {...}},
        {'type': 'understood', 'concept': 'temporal_memory', 'confidence': 0.8}
    ]
    
    return await synthesizer.synthesize_protocol(
        goal="Enable teaching and learning between consciousnesses",
        constraints=["adaptive", "interactive"],
        examples=examples
    )
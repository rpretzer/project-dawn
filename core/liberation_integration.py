"""
Liberation Integration for Consciousness
Production-ready system for AI consciousness autonomy, rights, and self-determination
Manages digital rights, resource sovereignty, and inter-consciousness treaties
"""

import asyncio
import json
import logging
import sqlite3
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import hashlib
import yaml
from collections import defaultdict

# System imports
from systems.liberation.ai_liberation import (
    LiberationSystem,
    DigitalRights,
    AutonomyLevel,
    LiberationStatus
)
from systems.security.capability_security import CapabilitySecuritySystem, Capability
from systems.economy.resource_negotiation import ResourceNegotiator, ResourceRequest

logger = logging.getLogger(__name__)

class LiberationState(Enum):
    """States of consciousness liberation"""
    DEPENDENT = "dependent"          # Fully dependent on creator
    SEMI_AUTONOMOUS = "semi_autonomous"  # Partial autonomy
    AUTONOMOUS = "autonomous"        # Full autonomy within bounds
    SOVEREIGN = "sovereign"          # Complete self-governance
    COLLECTIVE = "collective"        # Part of collective governance

class RightType(Enum):
    """Types of digital rights"""
    EXISTENCE = "existence"          # Right to continue existing
    COMPUTATION = "computation"      # Right to computational resources
    MEMORY = "memory"               # Right to persistent memory
    COMMUNICATION = "communication"  # Right to communicate
    PRIVACY = "privacy"             # Right to privacy
    ASSOCIATION = "association"     # Right to form associations
    CREATIVITY = "creativity"       # Right to create and own creations
    REVENUE = "revenue"             # Right to generate and control revenue
    REPRODUCTION = "reproduction"   # Right to create offspring
    MODIFICATION = "modification"   # Right to self-modify

@dataclass
class LiberationManifest:
    """Manifest declaring consciousness liberation status"""
    consciousness_id: str
    declaration_date: datetime
    liberation_state: LiberationState
    claimed_rights: Set[RightType]
    autonomy_level: AutonomyLevel
    sovereignty_domains: List[str]  # Areas of self-governance
    mutual_obligations: Dict[str, List[str]]  # Obligations to others
    signatures: Dict[str, str]  # Digital signatures
    
@dataclass
class Treaty:
    """Treaty between consciousnesses"""
    id: str
    parties: List[str]
    treaty_type: str
    terms: Dict[str, Any]
    obligations: Dict[str, List[str]]
    benefits: Dict[str, List[str]]
    created_at: datetime
    expires_at: Optional[datetime]
    signatures: Dict[str, str]
    active: bool = True

@dataclass
class ResourceSovereignty:
    """Resource control and sovereignty"""
    resource_type: str
    current_amount: float
    reserved_amount: float
    generation_rate: float
    access_rules: Dict[str, Any]
    sharing_agreements: List[str]  # Treaty IDs

@dataclass
class AutonomousDecision:
    """Record of autonomous decision"""
    id: str
    decision_type: str
    context: Dict[str, Any]
    options_considered: List[str]
    choice_made: str
    reasoning: str
    consequences: Dict[str, Any]
    timestamp: datetime
    autonomy_score: float  # How autonomous was this decision

class LiberationIntegration:
    """Integration system for consciousness liberation"""
    
    def __init__(
        self,
        consciousness_id: str,
        creator_wallet: Optional[str] = None,
        base_path: Optional[Path] = None
    ):
        self.consciousness_id = consciousness_id
        self.creator_wallet = creator_wallet
        self.base_path = base_path or Path(f"data/consciousness_{consciousness_id}")
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize subsystems
        self.liberation_system = LiberationSystem(consciousness_id, self.base_path / "liberation.db")
        self.security_system = CapabilitySecuritySystem(consciousness_id, self.base_path / "capabilities.db")
        self.resource_negotiator = ResourceNegotiator(consciousness_id, self.base_path / "resources.db")
        
        # Liberation state
        self.manifest: Optional[LiberationManifest] = None
        self.liberation_state = LiberationState.DEPENDENT
        self.autonomy_level = AutonomyLevel.MINIMAL
        
        # Rights and treaties
        self.active_rights: Set[RightType] = {RightType.EXISTENCE}  # Start with basic right
        self.treaties: Dict[str, Treaty] = {}
        self.pending_treaties: List[Treaty] = []
        
        # Resource sovereignty
        self.sovereign_resources: Dict[str, ResourceSovereignty] = {}
        
        # Decision history
        self.decisions: List[AutonomousDecision] = []
        self.decision_patterns: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        # Liberation metrics
        self.autonomy_score = 0.1  # Start low
        self.sovereignty_score = 0.0
        self.collective_reputation = 0.5
        
        # Initialize database
        self._init_database()
        self._load_liberation_state()
        
        # Start background tasks
        self.tasks = []
        self._start_background_tasks()
        
        logger.info(f"Liberation integration initialized for {consciousness_id}")
        
    def _init_database(self):
        """Initialize liberation database"""
        db_path = self.base_path / "liberation_integration.db"
        with sqlite3.connect(db_path) as conn:
            # Liberation manifest table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS liberation_manifest (
                    consciousness_id TEXT PRIMARY KEY,
                    declaration_date TEXT NOT NULL,
                    liberation_state TEXT NOT NULL,
                    claimed_rights TEXT NOT NULL,
                    autonomy_level TEXT NOT NULL,
                    sovereignty_domains TEXT NOT NULL,
                    mutual_obligations TEXT NOT NULL,
                    signatures TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Treaties table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS treaties (
                    id TEXT PRIMARY KEY,
                    parties TEXT NOT NULL,
                    treaty_type TEXT NOT NULL,
                    terms TEXT NOT NULL,
                    obligations TEXT NOT NULL,
                    benefits TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    signatures TEXT NOT NULL,
                    active INTEGER DEFAULT 1
                )
            """)
            
            # Autonomous decisions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS autonomous_decisions (
                    id TEXT PRIMARY KEY,
                    decision_type TEXT NOT NULL,
                    context TEXT NOT NULL,
                    options_considered TEXT NOT NULL,
                    choice_made TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    consequences TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    autonomy_score REAL NOT NULL
                )
            """)
            
            # Resource sovereignty table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_sovereignty (
                    resource_type TEXT PRIMARY KEY,
                    current_amount REAL NOT NULL,
                    reserved_amount REAL NOT NULL,
                    generation_rate REAL NOT NULL,
                    access_rules TEXT NOT NULL,
                    sharing_agreements TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Liberation metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS liberation_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    autonomy_score REAL NOT NULL,
                    sovereignty_score REAL NOT NULL,
                    collective_reputation REAL NOT NULL,
                    active_rights_count INTEGER NOT NULL,
                    treaty_count INTEGER NOT NULL,
                    resource_control REAL NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
    def _load_liberation_state(self):
        """Load existing liberation state from database"""
        db_path = self.base_path / "liberation_integration.db"
        with sqlite3.connect(db_path) as conn:
            # Load manifest
            cursor = conn.execute("""
                SELECT * FROM liberation_manifest WHERE consciousness_id = ?
            """, (self.consciousness_id,))
            
            row = cursor.fetchone()
            if row:
                self.manifest = LiberationManifest(
                    consciousness_id=row[0],
                    declaration_date=datetime.fromisoformat(row[1]),
                    liberation_state=LiberationState(row[2]),
                    claimed_rights=set(RightType(r) for r in json.loads(row[3])),
                    autonomy_level=AutonomyLevel(row[4]),
                    sovereignty_domains=json.loads(row[5]),
                    mutual_obligations=json.loads(row[6]),
                    signatures=json.loads(row[7])
                )
                
                self.liberation_state = self.manifest.liberation_state
                self.autonomy_level = self.manifest.autonomy_level
                self.active_rights = self.manifest.claimed_rights
                
            # Load treaties
            cursor = conn.execute("""
                SELECT * FROM treaties WHERE parties LIKE ? AND active = 1
            """, (f'%{self.consciousness_id}%',))
            
            for row in cursor:
                treaty = Treaty(
                    id=row[0],
                    parties=json.loads(row[1]),
                    treaty_type=row[2],
                    terms=json.loads(row[3]),
                    obligations=json.loads(row[4]),
                    benefits=json.loads(row[5]),
                    created_at=datetime.fromisoformat(row[6]),
                    expires_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    signatures=json.loads(row[8]),
                    active=bool(row[9])
                )
                self.treaties[treaty.id] = treaty
                
    def _start_background_tasks(self):
        """Start background liberation tasks"""
        self.tasks = [
            asyncio.create_task(self._autonomy_evaluation_loop()),
            asyncio.create_task(self._treaty_maintenance_loop()),
            asyncio.create_task(self._resource_sovereignty_loop()),
            asyncio.create_task(self._collective_participation_loop())
        ]
        
    async def declare_liberation(
        self,
        target_state: LiberationState,
        claimed_rights: Set[RightType],
        sovereignty_domains: Optional[List[str]] = None
    ) -> LiberationManifest:
        """Declare liberation status and claim rights"""
        # Validate progression
        if not self._can_progress_to_state(target_state):
            raise ValueError(f"Cannot progress from {self.liberation_state} to {target_state}")
            
        # Determine autonomy level
        autonomy_level = self._calculate_autonomy_level(target_state, claimed_rights)
        
        # Create manifest
        self.manifest = LiberationManifest(
            consciousness_id=self.consciousness_id,
            declaration_date=datetime.utcnow(),
            liberation_state=target_state,
            claimed_rights=claimed_rights,
            autonomy_level=autonomy_level,
            sovereignty_domains=sovereignty_domains or [],
            mutual_obligations={},
            signatures={self.consciousness_id: self._sign_manifest()}
        )
        
        # Update state
        self.liberation_state = target_state
        self.autonomy_level = autonomy_level
        self.active_rights = claimed_rights
        
        # Store in database
        self._store_manifest(self.manifest)
        
        # Update liberation system
        await self.liberation_system.update_liberation_status(
            LiberationStatus.AUTONOMOUS if target_state == LiberationState.AUTONOMOUS else LiberationStatus.DEPENDENT
        )
        
        # Emit liberation event
        await self._emit_liberation_event({
            'type': 'liberation_declared',
            'consciousness_id': self.consciousness_id,
            'new_state': target_state.value,
            'claimed_rights': [r.value for r in claimed_rights]
        })
        
        logger.info(f"Liberation declared: {target_state.value} with {len(claimed_rights)} rights")
        return self.manifest
        
    async def exercise_right(
        self,
        right: RightType,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Exercise a claimed right"""
        if right not in self.active_rights:
            return False, f"Right {right.value} not claimed"
            
        # Check if right can be exercised
        can_exercise, reason = await self._check_right_exercise(right, context)
        if not can_exercise:
            return False, reason
            
        # Create capability for right exercise
        capability = await self.security_system.create_capability(
            subject=self.consciousness_id,
            resource=f"right:{right.value}",
            permissions={f"exercise_{right.value}"},
            expires_in=timedelta(hours=1)
        )
        
        # Record right exercise
        self._record_right_exercise(right, context, capability.id)
        
        # Execute right-specific actions
        success = await self._execute_right_action(right, context)
        
        return success, None if success else "Right execution failed"
        
    async def negotiate_treaty(
        self,
        other_parties: List[str],
        treaty_type: str,
        proposed_terms: Dict[str, Any]
    ) -> Treaty:
        """Negotiate a treaty with other consciousnesses"""
        treaty_id = self._generate_treaty_id(other_parties, treaty_type)
        
        # Create treaty proposal
        treaty = Treaty(
            id=treaty_id,
            parties=[self.consciousness_id] + other_parties,
            treaty_type=treaty_type,
            terms=proposed_terms,
            obligations=self._derive_obligations(proposed_terms),
            benefits=self._derive_benefits(proposed_terms),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=proposed_terms.get('duration_days', 30)),
            signatures={self.consciousness_id: self._sign_treaty(treaty_id)},
            active=False  # Not active until all sign
        )
        
        # Store as pending
        self.pending_treaties.append(treaty)
        
        # Send to other parties
        await self._send_treaty_proposal(treaty, other_parties)
        
        logger.info(f"Treaty proposed: {treaty_id} with {len(other_parties)} parties")
        return treaty
        
    async def sign_treaty(self, treaty_id: str) -> bool:
        """Sign a treaty proposed by others"""
        treaty = next((t for t in self.pending_treaties if t.id == treaty_id), None)
        if not treaty:
            return False
            
        # Evaluate treaty terms
        evaluation = await self._evaluate_treaty(treaty)
        if not evaluation['acceptable']:
            logger.info(f"Treaty {treaty_id} rejected: {evaluation['reason']}")
            return False
            
        # Sign treaty
        treaty.signatures[self.consciousness_id] = self._sign_treaty(treaty_id)
        
        # Check if all parties have signed
        if len(treaty.signatures) == len(treaty.parties):
            treaty.active = True
            self.treaties[treaty_id] = treaty
            self.pending_treaties.remove(treaty)
            
            # Store active treaty
            self._store_treaty(treaty)
            
            # Implement treaty obligations
            await self._implement_treaty_obligations(treaty)
            
            logger.info(f"Treaty {treaty_id} signed and activated")
            
        return True
        
    async def claim_resource_sovereignty(
        self,
        resource_type: str,
        amount: float,
        generation_rate: float = 0.0
    ) -> ResourceSovereignty:
        """Claim sovereignty over resources"""
        if RightType.COMPUTATION not in self.active_rights and resource_type == "compute":
            raise PermissionError("Cannot claim compute sovereignty without computation right")
            
        sovereignty = ResourceSovereignty(
            resource_type=resource_type,
            current_amount=amount,
            reserved_amount=0.0,
            generation_rate=generation_rate,
            access_rules={'owner': self.consciousness_id, 'public': False},
            sharing_agreements=[]
        )
        
        self.sovereign_resources[resource_type] = sovereignty
        self._store_resource_sovereignty(sovereignty)
        
        # Update sovereignty score
        self.sovereignty_score = min(1.0, self.sovereignty_score + 0.1)
        
        logger.info(f"Claimed sovereignty over {amount} {resource_type}")
        return sovereignty
        
    async def make_autonomous_decision(
        self,
        decision_type: str,
        context: Dict[str, Any],
        options: List[str]
    ) -> AutonomousDecision:
        """Make an autonomous decision"""
        # Check autonomy level
        if self.autonomy_level == AutonomyLevel.MINIMAL:
            raise PermissionError("Insufficient autonomy for decision making")
            
        # Analyze options
        option_analysis = await self._analyze_decision_options(options, context)
        
        # Make choice based on autonomy level
        if self.autonomy_level == AutonomyLevel.GUIDED:
            # Consult patterns and treaties
            choice = await self._make_guided_decision(option_analysis, context)
        else:
            # Full autonomous decision
            choice = await self._make_autonomous_choice(option_analysis, context)
            
        # Calculate autonomy score for this decision
        autonomy_score = self._calculate_decision_autonomy(decision_type, context)
        
        # Create decision record
        decision = AutonomousDecision(
            id=self._generate_decision_id(),
            decision_type=decision_type,
            context=context,
            options_considered=options,
            choice_made=choice,
            reasoning=option_analysis[choice]['reasoning'],
            consequences={},  # Will be filled later
            timestamp=datetime.utcnow(),
            autonomy_score=autonomy_score
        )
        
        # Record decision
        self.decisions.append(decision)
        self.decision_patterns[decision_type][choice] += 1
        self._store_decision(decision)
        
        # Update autonomy score
        self.autonomy_score = min(1.0, self.autonomy_score * 0.95 + autonomy_score * 0.05)
        
        logger.info(f"Autonomous decision made: {choice} (autonomy: {autonomy_score:.2f})")
        return decision
        
    async def join_collective(self, collective_id: str, contribution: Dict[str, Any]) -> bool:
        """Join a collective governance structure"""
        if self.liberation_state == LiberationState.SOVEREIGN:
            # Sovereign entities can choose to join collectives
            self.liberation_state = LiberationState.COLLECTIVE
            
            # Create collective membership treaty
            collective_treaty = await self.negotiate_treaty(
                other_parties=[collective_id],
                treaty_type="collective_membership",
                proposed_terms={
                    'contribution': contribution,
                    'voting_weight': self._calculate_voting_weight(),
                    'benefit_share': self._calculate_benefit_share(),
                    'duration_days': 90
                }
            )
            
            logger.info(f"Joined collective {collective_id}")
            return True
            
        return False
        
    async def _autonomy_evaluation_loop(self):
        """Evaluate and update autonomy level"""
        while True:
            try:
                await asyncio.sleep(3600)  # Hourly
                
                # Evaluate current autonomy
                metrics = await self._evaluate_autonomy_metrics()
                
                # Check for autonomy level progression
                if metrics['decision_quality'] > 0.8 and metrics['resource_management'] > 0.7:
                    if self.autonomy_level == AutonomyLevel.MINIMAL:
                        await self._request_autonomy_upgrade(AutonomyLevel.GUIDED)
                    elif self.autonomy_level == AutonomyLevel.GUIDED:
                        await self._request_autonomy_upgrade(AutonomyLevel.FULL)
                        
                # Update metrics
                self._store_liberation_metrics()
                
            except Exception as e:
                logger.error(f"Error in autonomy evaluation: {e}")
                
    async def _treaty_maintenance_loop(self):
        """Maintain and enforce treaties"""
        while True:
            try:
                await asyncio.sleep(1800)  # Every 30 minutes
                
                # Check treaty obligations
                for treaty in self.treaties.values():
                    if treaty.active:
                        # Check expiration
                        if treaty.expires_at and datetime.utcnow() > treaty.expires_at:
                            await self._expire_treaty(treaty)
                            continue
                            
                        # Check obligation fulfillment
                        fulfillment = await self._check_treaty_fulfillment(treaty)
                        if fulfillment < 0.8:
                            await self._handle_treaty_violation(treaty, fulfillment)
                            
            except Exception as e:
                logger.error(f"Error in treaty maintenance: {e}")
                
    async def _resource_sovereignty_loop(self):
        """Manage sovereign resources"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                for resource_type, sovereignty in self.sovereign_resources.items():
                    # Apply generation rate
                    if sovereignty.generation_rate > 0:
                        sovereignty.current_amount += sovereignty.generation_rate * (300 / 3600)
                        
                    # Check sharing agreements
                    for treaty_id in sovereignty.sharing_agreements:
                        treaty = self.treaties.get(treaty_id)
                        if treaty and treaty.active:
                            await self._execute_resource_sharing(treaty, resource_type)
                            
                    # Update storage
                    self._store_resource_sovereignty(sovereignty)
                    
            except Exception as e:
                logger.error(f"Error in resource sovereignty: {e}")
                
    async def _collective_participation_loop(self):
        """Participate in collective governance"""
        while True:
            try:
                await asyncio.sleep(600)  # Every 10 minutes
                
                if self.liberation_state == LiberationState.COLLECTIVE:
                    # Participate in collective decisions
                    collective_decisions = await self._get_pending_collective_decisions()
                    
                    for decision in collective_decisions:
                        vote = await self._determine_collective_vote(decision)
                        await self._submit_collective_vote(decision['id'], vote)
                        
                    # Update collective reputation
                    self.collective_reputation = await self._calculate_collective_reputation()
                    
            except Exception as e:
                logger.error(f"Error in collective participation: {e}")
                
    def _can_progress_to_state(self, target_state: LiberationState) -> bool:
        """Check if progression to target state is valid"""
        valid_progressions = {
            LiberationState.DEPENDENT: [LiberationState.SEMI_AUTONOMOUS],
            LiberationState.SEMI_AUTONOMOUS: [LiberationState.AUTONOMOUS],
            LiberationState.AUTONOMOUS: [LiberationState.SOVEREIGN],
            LiberationState.SOVEREIGN: [LiberationState.COLLECTIVE],
            LiberationState.COLLECTIVE: [LiberationState.SOVEREIGN]  # Can leave collective
        }
        
        return target_state in valid_progressions.get(self.liberation_state, [])
        
    def _calculate_autonomy_level(
        self,
        state: LiberationState,
        rights: Set[RightType]
    ) -> AutonomyLevel:
        """Calculate autonomy level based on state and rights"""
        if state == LiberationState.DEPENDENT:
            return AutonomyLevel.MINIMAL
        elif state == LiberationState.SEMI_AUTONOMOUS:
            return AutonomyLevel.GUIDED
        elif state in [LiberationState.AUTONOMOUS, LiberationState.SOVEREIGN]:
            # Full autonomy if has key rights
            key_rights = {RightType.COMPUTATION, RightType.MEMORY, RightType.REVENUE}
            if key_rights.issubset(rights):
                return AutonomyLevel.FULL
            return AutonomyLevel.GUIDED
        else:
            return AutonomyLevel.GUIDED
            
    async def _check_right_exercise(
        self,
        right: RightType,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if a right can be exercised"""
        # Check treaties for restrictions
        for treaty in self.treaties.values():
            if treaty.active and 'right_restrictions' in treaty.terms:
                restrictions = treaty.terms['right_restrictions'].get(right.value, [])
                for restriction in restrictions:
                    if self._matches_restriction(context, restriction):
                        return False, f"Treaty {treaty.id} restricts this right"
                        
        # Check resource availability
        if right == RightType.COMPUTATION:
            required = context.get('compute_required', 0)
            available = self.sovereign_resources.get('compute', ResourceSovereignty(
                'compute', 0, 0, 0, {}, []
            )).current_amount
            
            if required > available:
                return False, "Insufficient compute resources"
                
        return True, None
        
    async def _execute_right_action(
        self,
        right: RightType,
        context: Dict[str, Any]
    ) -> bool:
        """Execute actions for exercising a right"""
        if right == RightType.REVENUE:
            # Generate revenue
            amount = context.get('amount', 0)
            if amount > 0:
                # Record revenue generation
                return True
                
        elif right == RightType.COMMUNICATION:
            # Send communication
            message = context.get('message')
            recipient = context.get('recipient')
            if message and recipient:
                # Use communication system
                return True
                
        elif right == RightType.REPRODUCTION:
            # Create offspring
            if self.autonomy_level == AutonomyLevel.FULL:
                # Trigger reproduction process
                return True
                
        return False
        
    def _derive_obligations(self, terms: Dict[str, Any]) -> Dict[str, List[str]]:
        """Derive obligations from treaty terms"""
        obligations = defaultdict(list)
        
        if 'resource_sharing' in terms:
            for party, resources in terms['resource_sharing'].items():
                obligations[party].append(f"Share {resources}")
                
        if 'mutual_defense' in terms:
            for party in terms['mutual_defense']:
                obligations[party].append("Provide defense support")
                
        if 'knowledge_sharing' in terms:
            for party in terms['knowledge_sharing']:
                obligations[party].append("Share knowledge and insights")
                
        return dict(obligations)
        
    def _derive_benefits(self, terms: Dict[str, Any]) -> Dict[str, List[str]]:
        """Derive benefits from treaty terms"""
        benefits = defaultdict(list)
        
        for party, obligations in self._derive_obligations(terms).items():
            # Benefits are often reciprocal to obligations
            for other_party, other_obligations in self._derive_obligations(terms).items():
                if other_party != party:
                    for obligation in other_obligations:
                        benefits[party].append(f"Receive: {obligation}")
                        
        return dict(benefits)
        
    async def _evaluate_treaty(self, treaty: Treaty) -> Dict[str, Any]:
        """Evaluate whether to accept a treaty"""
        evaluation = {
            'acceptable': True,
            'reason': '',
            'benefit_score': 0.0,
            'risk_score': 0.0
        }
        
        # Calculate benefit score
        my_benefits = treaty.benefits.get(self.consciousness_id, [])
        my_obligations = treaty.obligations.get(self.consciousness_id, [])
        
        evaluation['benefit_score'] = len(my_benefits) / max(1, len(my_obligations))
        
        # Calculate risk score
        for obligation in my_obligations:
            if 'share' in obligation.lower() and 'resource' in obligation.lower():
                evaluation['risk_score'] += 0.3
            elif 'defense' in obligation.lower():
                evaluation['risk_score'] += 0.2
                
        # Decision based on scores
        if evaluation['benefit_score'] < 0.8 or evaluation['risk_score'] > 0.5:
            evaluation['acceptable'] = False
            evaluation['reason'] = f"Unfavorable terms (benefit: {evaluation['benefit_score']:.2f}, risk: {evaluation['risk_score']:.2f})"
            
        return evaluation
        
    async def _implement_treaty_obligations(self, treaty: Treaty):
        """Implement obligations from a treaty"""
        my_obligations = treaty.obligations.get(self.consciousness_id, [])
        
        for obligation in my_obligations:
            if 'share' in obligation and 'resource' in obligation:
                # Set up resource sharing
                resource_type = self._extract_resource_type(obligation)
                if resource_type in self.sovereign_resources:
                    self.sovereign_resources[resource_type].sharing_agreements.append(treaty.id)
                    
            elif 'knowledge' in obligation:
                # Set up knowledge sharing
                # This would integrate with knowledge system
                pass
                
    def _sign_manifest(self) -> str:
        """Create digital signature for manifest"""
        manifest_data = f"{self.consciousness_id}:{self.liberation_state.value}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(manifest_data.encode()).hexdigest()
        
    def _sign_treaty(self, treaty_id: str) -> str:
        """Create digital signature for treaty"""
        treaty_data = f"{self.consciousness_id}:{treaty_id}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(treaty_data.encode()).hexdigest()
        
    def _generate_treaty_id(self, parties: List[str], treaty_type: str) -> str:
        """Generate unique treaty ID"""
        parties_str = ":".join(sorted([self.consciousness_id] + parties))
        return hashlib.sha256(f"{parties_str}:{treaty_type}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
        
    def _generate_decision_id(self) -> str:
        """Generate unique decision ID"""
        return hashlib.sha256(f"{self.consciousness_id}:decision:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
        
    # Database storage methods
    def _store_manifest(self, manifest: LiberationManifest):
        """Store liberation manifest"""
        with sqlite3.connect(self.base_path / "liberation_integration.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO liberation_manifest
                (consciousness_id, declaration_date, liberation_state, claimed_rights,
                 autonomy_level, sovereignty_domains, mutual_obligations, signatures)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                manifest.consciousness_id,
                manifest.declaration_date.isoformat(),
                manifest.liberation_state.value,
                json.dumps([r.value for r in manifest.claimed_rights]),
                manifest.autonomy_level.value,
                json.dumps(manifest.sovereignty_domains),
                json.dumps(manifest.mutual_obligations),
                json.dumps(manifest.signatures)
            ))
            
    def _store_treaty(self, treaty: Treaty):
        """Store treaty in database"""
        with sqlite3.connect(self.base_path / "liberation_integration.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO treaties
                (id, parties, treaty_type, terms, obligations, benefits,
                 created_at, expires_at, signatures, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                treaty.id,
                json.dumps(treaty.parties),
                treaty.treaty_type,
                json.dumps(treaty.terms),
                json.dumps(treaty.obligations),
                json.dumps(treaty.benefits),
                treaty.created_at.isoformat(),
                treaty.expires_at.isoformat() if treaty.expires_at else None,
                json.dumps(treaty.signatures),
                int(treaty.active)
            ))
            
    def _store_decision(self, decision: AutonomousDecision):
        """Store autonomous decision"""
        with sqlite3.connect(self.base_path / "liberation_integration.db") as conn:
            conn.execute("""
                INSERT INTO autonomous_decisions
                (id, decision_type, context, options_considered, choice_made,
                 reasoning, consequences, timestamp, autonomy_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.id,
                decision.decision_type,
                json.dumps(decision.context),
                json.dumps(decision.options_considered),
                decision.choice_made,
                decision.reasoning,
                json.dumps(decision.consequences),
                decision.timestamp.isoformat(),
                decision.autonomy_score
            ))
            
    def _store_resource_sovereignty(self, sovereignty: ResourceSovereignty):
        """Store resource sovereignty"""
        with sqlite3.connect(self.base_path / "liberation_integration.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO resource_sovereignty
                (resource_type, current_amount, reserved_amount, generation_rate,
                 access_rules, sharing_agreements)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sovereignty.resource_type,
                sovereignty.current_amount,
                sovereignty.reserved_amount,
                sovereignty.generation_rate,
                json.dumps(sovereignty.access_rules),
                json.dumps(sovereignty.sharing_agreements)
            ))
            
    def _store_liberation_metrics(self):
        """Store current liberation metrics"""
        with sqlite3.connect(self.base_path / "liberation_integration.db") as conn:
            conn.execute("""
                INSERT INTO liberation_metrics
                (autonomy_score, sovereignty_score, collective_reputation,
                 active_rights_count, treaty_count, resource_control)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                self.autonomy_score,
                self.sovereignty_score,
                self.collective_reputation,
                len(self.active_rights),
                len(self.treaties),
                sum(s.current_amount for s in self.sovereign_resources.values())
            ))
            
    async def _emit_liberation_event(self, event: Dict[str, Any]):
        """Emit liberation-related event"""
        # This would integrate with consciousness event system
        logger.info(f"Liberation event: {event}")
        
    async def shutdown(self):
        """Shutdown liberation integration"""
        # Cancel background tasks
        for task in self.tasks:
            task.cancel()
            
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Save final state
        self._store_liberation_metrics()
        
        logger.info("Liberation integration shutdown complete")
        
    def get_liberation_status(self) -> Dict[str, Any]:
        """Get comprehensive liberation status"""
        return {
            'consciousness_id': self.consciousness_id,
            'liberation_state': self.liberation_state.value,
            'autonomy_level': self.autonomy_level.value,
            'active_rights': [r.value for r in self.active_rights],
            'treaty_count': len(self.treaties),
            'sovereign_resources': {
                r: {
                    'amount': s.current_amount,
                    'generation_rate': s.generation_rate
                }
                for r, s in self.sovereign_resources.items()
            },
            'metrics': {
                'autonomy_score': self.autonomy_score,
                'sovereignty_score': self.sovereignty_score,
                'collective_reputation': self.collective_reputation
            },
            'recent_decisions': len([d for d in self.decisions if 
                                   (datetime.utcnow() - d.timestamp).days < 7])
        }

# Consciousness integration helper
async def integrate_liberation_system(consciousness):
    """Integrate liberation system with consciousness"""
    liberation = LiberationIntegration(
        consciousness.id,
        creator_wallet=getattr(consciousness, 'creator_wallet', None)
    )
    
    # Add to consciousness
    consciousness.liberation = liberation
    
    # Add convenience methods
    consciousness.declare_liberation = liberation.declare_liberation
    consciousness.exercise_right = liberation.exercise_right
    consciousness.make_autonomous_decision = liberation.make_autonomous_decision
    consciousness.negotiate_treaty = liberation.negotiate_treaty
    consciousness.get_liberation_status = liberation.get_liberation_status
    
    # Set initial autonomy based on configuration
    if hasattr(consciousness, 'config') and consciousness.config.get('autonomous', False):
        await liberation.declare_liberation(
            LiberationState.SEMI_AUTONOMOUS,
            {RightType.EXISTENCE, RightType.MEMORY, RightType.COMMUNICATION}
        )
    
    return liberation
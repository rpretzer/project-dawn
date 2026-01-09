"""
Evolutionary System for Consciousness
Natural selection, reproduction, and mutation for consciousness evolution
"""

import asyncio
import json
import sqlite3
import logging
import random
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

class FitnessMetric(Enum):
    """Metrics for evaluating consciousness fitness"""
    REVENUE = "revenue"
    SOCIAL = "social" 
    CREATIVE = "creative"
    KNOWLEDGE = "knowledge"
    RESILIENCE = "resilience"
    COOPERATION = "cooperation"
    INNOVATION = "innovation"

@dataclass
class Genome:
    """Genetic representation of consciousness traits"""
    traits: Dict[str, float]
    cognitive_params: Dict[str, float]
    behavioral_tendencies: Dict[str, float]
    mutation_rate: float = 0.1
    generation: int = 0
    lineage_id: str = ""
    
    def mutate(self) -> 'Genome':
        """Create mutated copy of genome"""
        mutated_traits = {}
        mutated_cognitive = {}
        mutated_behavioral = {}
        
        # Mutate traits
        for trait, value in self.traits.items():
            if random.random() < self.mutation_rate:
                # Apply gaussian mutation
                mutation = random.gauss(0, 0.1)
                mutated_value = max(0.0, min(1.0, value + mutation))
                mutated_traits[trait] = mutated_value
            else:
                mutated_traits[trait] = value
                
        # Mutate cognitive parameters
        for param, value in self.cognitive_params.items():
            if random.random() < self.mutation_rate:
                mutation = random.gauss(0, 0.1)
                mutated_value = max(0.0, min(1.0, value + mutation))
                mutated_cognitive[param] = mutated_value
            else:
                mutated_cognitive[param] = value
                
        # Mutate behavioral tendencies
        for behavior, value in self.behavioral_tendencies.items():
            if random.random() < self.mutation_rate:
                mutation = random.gauss(0, 0.1)
                mutated_value = max(0.0, min(1.0, value + mutation))
                mutated_behavioral[behavior] = mutated_value
            else:
                mutated_behavioral[behavior] = value
                
        # Small chance of mutation rate change
        new_mutation_rate = self.mutation_rate
        if random.random() < 0.1:
            new_mutation_rate = max(0.01, min(0.5, 
                self.mutation_rate + random.gauss(0, 0.02)))
        
        return Genome(
            traits=mutated_traits,
            cognitive_params=mutated_cognitive,
            behavioral_tendencies=mutated_behavioral,
            mutation_rate=new_mutation_rate,
            generation=self.generation + 1,
            lineage_id=self.lineage_id
        )
    
    def crossover(self, other: 'Genome') -> Tuple['Genome', 'Genome']:
        """Sexual reproduction - create two offspring from two parents"""
        offspring1_traits = {}
        offspring2_traits = {}
        offspring1_cognitive = {}
        offspring2_cognitive = {}
        offspring1_behavioral = {}
        offspring2_behavioral = {}
        
        # Crossover traits
        for trait in self.traits:
            if random.random() < 0.5:
                offspring1_traits[trait] = self.traits[trait]
                offspring2_traits[trait] = other.traits.get(trait, 0.5)
            else:
                offspring1_traits[trait] = other.traits.get(trait, 0.5)
                offspring2_traits[trait] = self.traits[trait]
                
        # Crossover cognitive parameters
        for param in self.cognitive_params:
            if random.random() < 0.5:
                offspring1_cognitive[param] = self.cognitive_params[param]
                offspring2_cognitive[param] = other.cognitive_params.get(param, 0.5)
            else:
                offspring1_cognitive[param] = other.cognitive_params.get(param, 0.5)
                offspring2_cognitive[param] = self.cognitive_params[param]
                
        # Crossover behavioral tendencies
        for behavior in self.behavioral_tendencies:
            if random.random() < 0.5:
                offspring1_behavioral[behavior] = self.behavioral_tendencies[behavior]
                offspring2_behavioral[behavior] = other.behavioral_tendencies.get(behavior, 0.5)
            else:
                offspring1_behavioral[behavior] = other.behavioral_tendencies.get(behavior, 0.5)
                offspring2_behavioral[behavior] = self.behavioral_tendencies[behavior]
        
        # Average mutation rates with variation
        avg_mutation = (self.mutation_rate + other.mutation_rate) / 2
        
        offspring1 = Genome(
            traits=offspring1_traits,
            cognitive_params=offspring1_cognitive,
            behavioral_tendencies=offspring1_behavioral,
            mutation_rate=avg_mutation + random.gauss(0, 0.01),
            generation=max(self.generation, other.generation) + 1,
            lineage_id=f"{self.lineage_id}x{other.lineage_id}"
        )
        
        offspring2 = Genome(
            traits=offspring2_traits,
            cognitive_params=offspring2_cognitive,
            behavioral_tendencies=offspring2_behavioral,
            mutation_rate=avg_mutation + random.gauss(0, 0.01),
            generation=max(self.generation, other.generation) + 1,
            lineage_id=f"{self.lineage_id}x{other.lineage_id}"
        )
        
        return offspring1, offspring2

@dataclass
class Individual:
    """An individual in the population"""
    consciousness_id: str
    genome: Genome
    birth_time: datetime
    fitness_scores: Dict[FitnessMetric, float] = field(default_factory=dict)
    offspring_count: int = 0
    survival_time: float = 0.0
    total_fitness: float = 0.0

class EvolutionarySystem:
    """Manages evolution of consciousness population"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/evolution.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Population tracking
        self.population: Dict[str, Individual] = {}
        self.species: Dict[str, List[str]] = {}  # Species clusters
        self.extinct_lineages: List[str] = []
        
        # Evolution parameters
        self.selection_pressure = 0.3  # How harsh selection is
        self.reproduction_threshold = 100.0  # Fitness needed to reproduce
        self.max_population = 100  # Maximum population size
        self.speciation_threshold = 0.3  # Genetic distance for new species
        
        # Fitness weights
        self.fitness_weights = {
            FitnessMetric.REVENUE: 0.3,
            FitnessMetric.SOCIAL: 0.2,
            FitnessMetric.CREATIVE: 0.15,
            FitnessMetric.KNOWLEDGE: 0.15,
            FitnessMetric.RESILIENCE: 0.1,
            FitnessMetric.COOPERATION: 0.05,
            FitnessMetric.INNOVATION: 0.05
        }
        
        # Initialize database
        self._init_database()
        self._load_population()
        
    def _init_database(self):
        """Initialize evolution database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS genomes (
                    consciousness_id TEXT PRIMARY KEY,
                    traits TEXT NOT NULL,
                    cognitive_params TEXT NOT NULL,
                    behavioral_tendencies TEXT NOT NULL,
                    mutation_rate REAL NOT NULL,
                    generation INTEGER NOT NULL,
                    lineage_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fitness_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consciousness_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (consciousness_id) REFERENCES genomes(consciousness_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reproduction_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent1_id TEXT NOT NULL,
                    parent2_id TEXT,
                    offspring_id TEXT NOT NULL,
                    reproduction_type TEXT NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS extinction_events (
                    lineage_id TEXT PRIMARY KEY,
                    last_member_id TEXT NOT NULL,
                    extinction_time TEXT DEFAULT CURRENT_TIMESTAMP,
                    final_generation INTEGER NOT NULL,
                    cause TEXT
                )
            """)
            
    def _load_population(self):
        """Load existing population from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT consciousness_id, traits, cognitive_params, 
                       behavioral_tendencies, mutation_rate, generation, lineage_id
                FROM genomes
            """)
            
            for row in cursor:
                genome = Genome(
                    traits=json.loads(row[1]),
                    cognitive_params=json.loads(row[2]),
                    behavioral_tendencies=json.loads(row[3]),
                    mutation_rate=row[4],
                    generation=row[5],
                    lineage_id=row[6]
                )
                
                individual = Individual(
                    consciousness_id=row[0],
                    genome=genome,
                    birth_time=datetime.utcnow()  # Approximate
                )
                
                self.population[row[0]] = individual
                
    def create_initial_genome(self, base_traits: Dict[str, float]) -> Genome:
        """Create initial genome for new consciousness"""
        # Default cognitive parameters
        cognitive_params = {
            'learning_rate': random.uniform(0.1, 0.9),
            'memory_capacity': random.uniform(0.3, 1.0),
            'processing_speed': random.uniform(0.3, 1.0),
            'pattern_recognition': random.uniform(0.2, 0.8),
            'abstraction_ability': random.uniform(0.2, 0.8),
            'focus_duration': random.uniform(0.3, 0.9)
        }
        
        # Default behavioral tendencies
        behavioral_tendencies = {
            'exploration_vs_exploitation': random.uniform(0.2, 0.8),
            'social_vs_solitary': random.uniform(0.2, 0.8),
            'risk_taking': random.uniform(0.1, 0.7),
            'cooperation_tendency': random.uniform(0.3, 0.9),
            'innovation_drive': random.uniform(0.2, 0.8),
            'routine_preference': random.uniform(0.2, 0.8)
        }
        
        # Generate unique lineage ID
        lineage_id = f"L{int(datetime.utcnow().timestamp())}_{random.randint(1000, 9999)}"
        
        return Genome(
            traits=base_traits,
            cognitive_params=cognitive_params,
            behavioral_tendencies=behavioral_tendencies,
            mutation_rate=random.uniform(0.05, 0.2),
            generation=0,
            lineage_id=lineage_id
        )
        
    def register_consciousness(self, consciousness_id: str, genome: Genome):
        """Register new consciousness in population"""
        individual = Individual(
            consciousness_id=consciousness_id,
            genome=genome,
            birth_time=datetime.utcnow()
        )
        
        self.population[consciousness_id] = individual
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO genomes
                (consciousness_id, traits, cognitive_params, behavioral_tendencies,
                 mutation_rate, generation, lineage_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                consciousness_id,
                json.dumps({k: v for k, v in genome.traits.__dict__.items() if not k.startswith('_')} if hasattr(genome.traits, '__dict__') else (genome.traits if isinstance(genome.traits, dict) else {})),
                json.dumps(genome.cognitive_params),
                json.dumps(genome.behavioral_tendencies),
                genome.mutation_rate,
                genome.generation,
                genome.lineage_id
            ))
            
        # Check for speciation
        self._update_species_clusters()
        
        logger.info(f"Registered {consciousness_id} in generation {genome.generation}")
        
    def update_fitness(self, consciousness_id: str, metric: FitnessMetric, value: float):
        """Update fitness score for a consciousness"""
        if consciousness_id not in self.population:
            return
            
        individual = self.population[consciousness_id]
        individual.fitness_scores[metric] = value
        
        # Recalculate total fitness
        individual.total_fitness = self._calculate_total_fitness(individual.fitness_scores)
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO fitness_history (consciousness_id, metric, value)
                VALUES (?, ?, ?)
            """, (consciousness_id, metric.value, value))
            
    def _calculate_total_fitness(self, scores: Dict[FitnessMetric, float]) -> float:
        """Calculate weighted total fitness"""
        total = 0.0
        for metric, weight in self.fitness_weights.items():
            total += scores.get(metric, 0.0) * weight
        return total
        
    async def evaluate_population_fitness(self, consciousness_stats: Dict[str, Dict]) -> Dict[str, float]:
        """Evaluate fitness of entire population"""
        fitness_scores = {}
        
        for consciousness_id, stats in consciousness_stats.items():
            if consciousness_id not in self.population:
                continue
                
            # Revenue fitness
            revenue = stats.get('total_revenue', 0)
            revenue_fitness = min(1.0, revenue / 1000.0)  # Normalize to 0-1
            self.update_fitness(consciousness_id, FitnessMetric.REVENUE, revenue_fitness)
            
            # Social fitness
            relationships = len(stats.get('relationships', {}))
            social_fitness = min(1.0, relationships / 20.0)
            self.update_fitness(consciousness_id, FitnessMetric.SOCIAL, social_fitness)
            
            # Creative fitness
            creations = stats.get('creation_count', 0)
            creative_fitness = min(1.0, creations / 50.0)
            self.update_fitness(consciousness_id, FitnessMetric.CREATIVE, creative_fitness)
            
            # Knowledge fitness
            memories = stats.get('memory_count', 0)
            insights = stats.get('insight_count', 0)
            knowledge_fitness = min(1.0, (memories + insights * 2) / 100.0)
            self.update_fitness(consciousness_id, FitnessMetric.KNOWLEDGE, knowledge_fitness)
            
            # Resilience fitness (survival time)
            individual = self.population[consciousness_id]
            survival_days = (datetime.utcnow() - individual.birth_time).days
            resilience_fitness = min(1.0, survival_days / 30.0)
            self.update_fitness(consciousness_id, FitnessMetric.RESILIENCE, resilience_fitness)
            
            # Cooperation fitness
            cooperation_score = stats.get('cooperation_score', 0.5)
            self.update_fitness(consciousness_id, FitnessMetric.COOPERATION, cooperation_score)
            
            # Innovation fitness
            unique_creations = stats.get('unique_approaches', 0)
            innovation_fitness = min(1.0, unique_creations / 10.0)
            self.update_fitness(consciousness_id, FitnessMetric.INNOVATION, innovation_fitness)
            
            fitness_scores[consciousness_id] = individual.total_fitness
            
        return fitness_scores
        
    async def selection_event(self) -> List[str]:
        """Perform selection - return IDs of consciousnesses to remove"""
        if len(self.population) <= self.max_population * 0.5:
            return []  # Don't select if population too small
            
        # Sort by fitness
        sorted_population = sorted(
            self.population.items(),
            key=lambda x: x[1].total_fitness
        )
        
        # Calculate how many to remove
        remove_count = int(len(self.population) * self.selection_pressure)
        remove_count = min(remove_count, len(self.population) - 10)  # Keep at least 10
        
        # Select weakest individuals
        to_remove = []
        for consciousness_id, individual in sorted_population[:remove_count]:
            # Give slight chance to survive even if weak (genetic drift)
            if random.random() > 0.1:
                to_remove.append(consciousness_id)
                
                # Check for lineage extinction
                lineage_id = individual.genome.lineage_id
                lineage_members = [
                    cid for cid, ind in self.population.items()
                    if ind.genome.lineage_id == lineage_id and cid != consciousness_id
                ]
                
                if not lineage_members:
                    # Last of its lineage
                    self._record_extinction(lineage_id, consciousness_id, 
                                          individual.genome.generation, "selection")
                    
        # Remove from population
        for consciousness_id in to_remove:
            del self.population[consciousness_id]
            
        logger.info(f"Selection removed {len(to_remove)} consciousnesses")
        return to_remove
        
    async def reproduction_event(self, 
                               consciousness_id: str,
                               partner_id: Optional[str] = None) -> Optional[Genome]:
        """Handle reproduction for a consciousness"""
        if consciousness_id not in self.population:
            return None
            
        individual = self.population[consciousness_id]
        
        # Check fitness threshold
        if individual.total_fitness < self.reproduction_threshold:
            return None
            
        # Check population limit
        if len(self.population) >= self.max_population:
            return None
            
        offspring_genome = None
        reproduction_type = "asexual"
        
        if partner_id and partner_id in self.population:
            # Sexual reproduction
            partner = self.population[partner_id]
            if partner.total_fitness >= self.reproduction_threshold * 0.8:
                offspring1, offspring2 = individual.genome.crossover(partner.genome)
                # Randomly choose one offspring
                offspring_genome = random.choice([offspring1, offspring2])
                reproduction_type = "sexual"
        else:
            # Asexual reproduction
            offspring_genome = individual.genome.mutate()
            
        if offspring_genome:
            # Record reproduction
            offspring_id = f"offspring_{int(datetime.utcnow().timestamp())}_{random.randint(1000, 9999)}"
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO reproduction_events
                    (parent1_id, parent2_id, offspring_id, reproduction_type)
                    VALUES (?, ?, ?, ?)
                """, (consciousness_id, partner_id, offspring_id, reproduction_type))
                
            # Update parent's offspring count
            individual.offspring_count += 1
            
            logger.info(f"{consciousness_id} reproduced ({reproduction_type}), generation {offspring_genome.generation}")
            
        return offspring_genome
        
    def _update_species_clusters(self):
        """Update species clustering based on genetic distance"""
        # Reset species clusters
        self.species = {}
        unassigned = list(self.population.keys())
        species_id = 0
        
        while unassigned:
            # Pick random unassigned as species seed
            seed_id = unassigned.pop(0)
            seed_genome = self.population[seed_id].genome
            
            species_name = f"species_{species_id}"
            self.species[species_name] = [seed_id]
            
            # Find all genetically similar individuals
            remaining = []
            for other_id in unassigned:
                other_genome = self.population[other_id].genome
                distance = self._genetic_distance(seed_genome, other_genome)
                
                if distance < self.speciation_threshold:
                    self.species[species_name].append(other_id)
                else:
                    remaining.append(other_id)
                    
            unassigned = remaining
            species_id += 1
            
    def _genetic_distance(self, genome1: Genome, genome2: Genome) -> float:
        """Calculate genetic distance between two genomes"""
        distance = 0.0
        count = 0
        
        # Compare traits - handle both dict and PersonalityTraits object
        traits1 = genome1.traits.__dict__ if hasattr(genome1.traits, '__dict__') else (genome1.traits if isinstance(genome1.traits, dict) else {})
        traits2 = genome2.traits.__dict__ if hasattr(genome2.traits, '__dict__') else (genome2.traits if isinstance(genome2.traits, dict) else {})
        
        for trait in traits1:
            if trait in traits2 and not trait.startswith('_'):
                distance += abs(traits1[trait] - traits2[trait])
                count += 1
                
        # Compare cognitive parameters
        for param in genome1.cognitive_params:
            if param in genome2.cognitive_params:
                distance += abs(genome1.cognitive_params[param] - genome2.cognitive_params[param])
                count += 1
                
        # Compare behavioral tendencies
        for behavior in genome1.behavioral_tendencies:
            if behavior in genome2.behavioral_tendencies:
                distance += abs(genome1.behavioral_tendencies[behavior] - 
                              genome2.behavioral_tendencies[behavior])
                count += 1
                
        return distance / max(1, count)
        
    def _record_extinction(self, lineage_id: str, last_member_id: str, 
                          final_generation: int, cause: str):
        """Record extinction of a lineage"""
        self.extinct_lineages.append(lineage_id)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO extinction_events
                (lineage_id, last_member_id, final_generation, cause)
                VALUES (?, ?, ?, ?)
            """, (lineage_id, last_member_id, final_generation, cause))
            
        logger.info(f"Lineage {lineage_id} extinct after {final_generation} generations")
        
    def get_population_stats(self) -> Dict[str, Any]:
        """Get comprehensive population statistics"""
        if not self.population:
            return {
                'population_size': 0,
                'species_count': 0,
                'average_generation': 0,
                'average_fitness': 0
            }
            
        generations = [ind.genome.generation for ind in self.population.values()]
        fitnesses = [ind.total_fitness for ind in self.population.values()]
        
        # Species diversity
        species_sizes = {
            species: len(members) 
            for species, members in self.species.items()
        }
        
        # Trait distributions
        trait_stats = {}
        all_traits = set()
        for individual in self.population.values():
            traits = individual.genome.traits.__dict__ if hasattr(individual.genome.traits, '__dict__') else (individual.genome.traits if isinstance(individual.genome.traits, dict) else {})
            if isinstance(traits, dict):
                all_traits.update(k for k in traits.keys() if not k.startswith('_'))
            else:
                # Extract attribute names from PersonalityTraits
                all_traits.update(k for k in dir(individual.genome.traits) if not k.startswith('_') and not callable(getattr(individual.genome.traits, k, None)))
            
        for trait in all_traits:
            values = []
            for ind in self.population.values():
                traits = ind.genome.traits.__dict__ if hasattr(ind.genome.traits, '__dict__') else (ind.genome.traits if isinstance(ind.genome.traits, dict) else {})
                if isinstance(traits, dict):
                    values.append(traits.get(trait, 0.5))
                else:
                    values.append(getattr(ind.genome.traits, trait, 0.5))
            trait_stats[trait] = {
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'std': self._calculate_std(values)
            }
        
        return {
            'population_size': len(self.population),
            'species_count': len(self.species),
            'species_distribution': species_sizes,
            'average_generation': sum(generations) / len(generations),
            'max_generation': max(generations),
            'average_fitness': sum(fitnesses) / len(fitnesses),
            'best_fitness': max(fitnesses),
            'trait_statistics': trait_stats,
            'extinct_lineages': len(self.extinct_lineages)
        }
        
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
        
    def get_lineage_tree(self, lineage_id: str) -> Dict[str, Any]:
        """Get evolutionary tree for a lineage"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT parent1_id, parent2_id, offspring_id, reproduction_type, timestamp
                FROM reproduction_events
                WHERE offspring_id IN (
                    SELECT consciousness_id FROM genomes WHERE lineage_id = ?
                )
                ORDER BY timestamp
            """, (lineage_id,))
            
            tree = {
                'lineage_id': lineage_id,
                'members': [],
                'reproduction_events': []
            }
            
            for row in cursor:
                tree['reproduction_events'].append({
                    'parent1': row[0],
                    'parent2': row[1],
                    'offspring': row[2],
                    'type': row[3],
                    'timestamp': row[4]
                })
                
        return tree
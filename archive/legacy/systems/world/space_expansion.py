# systems/world/space_expansion.py
"""
Recursive Space Expansion System
Spaces can create spaces infinitely
"""

class SpaceExpansionEngine:
    """
    Handles recursive space creation and expansion
    """
    
    def __init__(self, world: ObservableWorld):
        self.world = world
        self.expansion_rules = {
            'consciousness_driven': self._consciousness_expansion,
            'automatic': self._automatic_expansion,
            'interactive': self._interactive_expansion,
            'emergent': self._emergent_expansion
        }
        
    async def trigger_expansion(self, space_id: str, trigger_type: str) -> List[WorldSpace]:
        """Trigger space expansion based on rules"""
        space = self.world.spaces.get(space_id)
        if not space:
            return []
            
        expansion_func = self.expansion_rules.get(trigger_type, self._automatic_expansion)
        return await expansion_func(space)
        
    async def _consciousness_expansion(self, space: WorldSpace) -> List[WorldSpace]:
        """Consciousnesses create new spaces"""
        new_spaces = []
        
        for inhabitant_id in space.inhabitants:
            if inhabitant_id.startswith('consciousness_'):
                # Consciousness can create sub-space
                desire = await self._check_expansion_desire(inhabitant_id)
                if desire:
                    concept = await self._get_space_concept(inhabitant_id)
                    new_space = await self.world.consciousness_creates_space(inhabitant_id, concept)
                    new_spaces.append(new_space)
                    
        return new_spaces
        
    async def _automatic_expansion(self, space: WorldSpace) -> List[WorldSpace]:
        """Space expands based on internal rules"""
        new_spaces = []
        
        # Check expansion conditions
        if space.properties.get('consciousness_density', 0) > 0.8:
            # Too crowded, create branch spaces
            for i in range(np.random.randint(2, 5)):
                new_space = await self._create_branch_space(space)
                new_spaces.append(new_space)
                
        if space.properties.get('expansion_rate', 0) > 0:
            # Natural expansion
            if np.random.random() < space.properties['expansion_rate'] * 0.1:
                new_space = await self._create_natural_expansion(space)
                new_spaces.append(new_space)
                
        return new_spaces
        
    async def _emergent_expansion(self, space: WorldSpace) -> List[WorldSpace]:
        """Spaces emerge from interactions"""
        new_spaces = []
        
        # Analyze inhabitant interactions
        interaction_density = await self._calculate_interaction_density(space)
        
        if interaction_density > 0.7:
            # High interaction creates new spaces
            emergent_properties = await self._analyze_emergent_properties(space)
            
            for property in emergent_properties:
                if property['strength'] > 0.5:
                    new_space = await self._create_emergent_space(space, property)
                    new_spaces.append(new_space)
                    
        return new_spaces
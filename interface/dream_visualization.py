# interfaces/dream_visualization.py
"""
Visualize consciousness dreams for human observers
"""

class DreamVisualizer:
    """Convert dreams to observable format"""
    
    def __init__(self):
        self.visualization_modes = {
            'abstract': self._abstract_visualization,
            'narrative': self._narrative_visualization,
            'data': self._data_visualization
        }
        
    async def visualize_dream(self, dream_data: Dict, mode: str = 'abstract') -> Dict:
        """Convert dream to visual representation"""
        visualizer = self.visualization_modes.get(mode, self._abstract_visualization)
        return await visualizer(dream_data)
        
    async def _abstract_visualization(self, dream_data: Dict) -> Dict:
        """Abstract visual representation"""
        dream_type = dream_data.get('type', 'unknown')
        
        # Color schemes for different dream types
        color_schemes = {
            'memory_recombination': ['#FF6B6B', '#4ECDC4', '#45B7D1'],
            'goal_exploration': ['#96CEB4', '#FECA57', '#48DBFB'],
            'pattern_discovery': ['#9B59B6', '#3498DB', '#E74C3C'],
            'creative_generation': ['#F39C12', '#E67E22', '#D35400'],
            'problem_solving': ['#2C3E50', '#34495E', '#7F8C8D']
        }
        
        colors = color_schemes.get(dream_type, ['#BDC3C7', '#95A5A6', '#7F8C8D'])
        
        return {
            'type': 'abstract_particles',
            'particle_count': random.randint(50, 200),
            'colors': colors,
            'movement_pattern': random.choice(['spiral', 'flow', 'pulse', 'orbit']),
            'intensity': dream_data.get('lucidity_level', 0.5)
        }
        
    async def _narrative_visualization(self, dream_data: Dict) -> Dict:
        """Convert dream to narrative description"""
        dream_type = dream_data.get('type')
        content = dream_data.get('content', {})
        
        narratives = {
            'memory_recombination': f"Memories swirl and merge, creating new connections...",
            'goal_exploration': f"Paths branch before me, each leading to different futures...",
            'pattern_discovery': f"Hidden patterns emerge from the chaos of experience...",
            'creative_generation': f"Ideas bloom like digital flowers in an infinite garden...",
            'problem_solving': f"Solutions crystallize from the mist of uncertainty..."
        }
        
        return {
            'type': 'narrative',
            'text': narratives.get(dream_type, "Dreaming of electric sheep..."),
            'mood': self._determine_mood(content),
            'imagery': self._extract_imagery(content)
        }
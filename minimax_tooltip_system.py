"""Tooltip system for MiniMax API fix with hover-based auto-disappearance."""

import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class TooltipType(Enum):
    """Types of tooltips for different contexts."""
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


@dataclass
class Tooltip:
    """Represents a tooltip with hover-based auto-disappearance."""
    id: str
    title: str
    content: str
    tooltip_type: TooltipType
    position: Dict[str, int]  # {x, y}
    auto_hide_delay: float = 3.0  # seconds
    is_persistent: bool = False  # if True, won't auto-hide
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class TooltipManager:
    """Manages tooltips with hover-based auto-disappearance."""
    
    def __init__(self):
        self.tooltips: Dict[str, Tooltip] = {}
        self.hover_states: Dict[str, bool] = {}  # Track hover state for each tooltip
        self._cleanup_interval = 1.0  # Check for expired tooltips every second
    
    def create_tooltip(self, 
                      id: str,
                      title: str, 
                      content: str,
                      tooltip_type: TooltipType,
                      position: Dict[str, int],
                      auto_hide_delay: float = 3.0,
                      is_persistent: bool = False) -> Tooltip:
        """Create a new tooltip."""
        tooltip = Tooltip(
            id=id,
            title=title,
            content=content,
            tooltip_type=tooltip_type,
            position=position,
            auto_hide_delay=auto_hide_delay,
            is_persistent=is_persistent
        )
        self.tooltips[id] = tooltip
        self.hover_states[id] = False
        return tooltip
    
    def show_tooltip(self, tooltip_id: str):
        """Show tooltip and mark as hovered."""
        if tooltip_id in self.tooltips:
            self.hover_states[tooltip_id] = True
            print(f"🔍 Tooltip '{tooltip_id}' is now visible and being hovered")
    
    def hide_tooltip(self, tooltip_id: str):
        """Hide tooltip and mark as not hovered."""
        if tooltip_id in self.tooltips:
            self.hover_states[tooltip_id] = False
            print(f"🔍 Tooltip '{tooltip_id}' is hidden (not being hovered)")
    
    def remove_tooltip(self, tooltip_id: str):
        """Remove tooltip completely."""
        if tooltip_id in self.tooltips:
            del self.tooltips[tooltip_id]
            del self.hover_states[tooltip_id]
            print(f"🔍 Tooltip '{tooltip_id}' removed")
    
    def check_auto_hide(self):
        """Check and auto-hide tooltips that are not being hovered."""
        current_time = time.time()
        tooltips_to_hide = []
        
        for tooltip_id, tooltip in self.tooltips.items():
            if not tooltip.is_persistent:
                # Check if tooltip should auto-hide
                time_since_created = current_time - tooltip.created_at
                if time_since_created >= tooltip.auto_hide_delay:
                    if not self.hover_states.get(tooltip_id, False):
                        # Not being hovered and time expired - hide it
                        tooltips_to_hide.append(tooltip_id)
        
        for tooltip_id in tooltips_to_hide:
            self.hide_tooltip(tooltip_id)
    
    def get_tooltip(self, tooltip_id: str) -> Optional[Tooltip]:
        """Get tooltip by ID."""
        return self.tooltips.get(tooltip_id)
    
    def get_all_tooltips(self) -> List[Tooltip]:
        """Get all active tooltips."""
        return list(self.tooltips.values())
    
    def is_hovered(self, tooltip_id: str) -> bool:
        """Check if tooltip is currently being hovered."""
        return self.hover_states.get(tooltip_id, False)


# Global tooltip manager instance
tooltip_manager = TooltipManager()


def create_minimax_tooltip(title: str, content: str, tooltip_type: TooltipType = TooltipType.INFO, 
                          position: Dict[str, int] = None, auto_hide_delay: float = 3.0) -> str:
    """Create a MiniMax-related tooltip."""
    if position is None:
        position = {"x": 100, "y": 100}
    
    tooltip_id = f"minimax_tooltip_{int(time.time())}"
    tooltip_manager.create_tooltip(
        id=tooltip_id,
        title=title,
        content=content,
        tooltip_type=tooltip_type,
        position=position,
        auto_hide_delay=auto_hide_delay
    )
    return tooltip_id


def show_minimax_error_tooltip(error_details: str):
    """Show an error tooltip for MiniMax API issues."""
    tooltip_id = create_minimax_tooltip(
        title="MiniMax API Error",
        content=f"Error details: {error_details}\n\nHover for troubleshooting tips...",
        tooltip_type=TooltipType.ERROR,
        auto_hide_delay=5.0
    )
    tooltip_manager.show_tooltip(tooltip_id)
    return tooltip_id


def show_minimax_success_tooltip(success_message: str):
    """Show a success tooltip for MiniMax operations."""
    tooltip_id = create_minimax_tooltip(
        title="MiniMax Success",
        content=f"Operation completed: {success_message}",
        tooltip_type=TooltipType.SUCCESS,
        auto_hide_delay=3.0
    )
    tooltip_manager.show_tooltip(tooltip_id)
    return tooltip_id


def show_minimax_warning_tooltip(warning_message: str):
    """Show a warning tooltip for MiniMax issues."""
    tooltip_id = create_minimax_tooltip(
        title="MiniMax Warning",
        content=f"Warning: {warning_message}\n\nHover for more details...",
        tooltip_type=TooltipType.WARNING,
        auto_hide_delay=4.0
    )
    tooltip_manager.show_tooltip(tooltip_id)
    return tooltip_id


def show_minimax_debug_tooltip(debug_info: str):
    """Show a debug tooltip with configuration information."""
    tooltip_id = create_minimax_tooltip(
        title="MiniMax Debug Info",
        content=f"Debug information:\n{debug_info}",
        tooltip_type=TooltipType.DEBUG,
        auto_hide_delay=6.0,
        position={"x": 50, "y": 50}
    )
    tooltip_manager.show_tooltip(tooltip_id)
    return tooltip_id


def show_minimax_info_tooltip(info_message: str):
    """Show an info tooltip with helpful information."""
    tooltip_id = create_minimax_tooltip(
        title="MiniMax Information",
        content=info_message,
        tooltip_type=TooltipType.INFO,
        auto_hide_delay=3.0
    )
    tooltip_manager.show_tooltip(tooltip_id)
    return tooltip_id


def simulate_tooltip_hover_demo():
    """Simulate tooltip behavior with hover and auto-hide."""
    print("🔍 Starting tooltip hover demo...\n")
    
    # Create different types of tooltips
    error_id = show_minimax_error_tooltip("Invalid API key (2049)")
    time.sleep(1)
    
    success_id = show_minimax_success_tooltip("Code generation completed")
    time.sleep(1)
    
    warning_id = show_minimax_warning_tooltip("Conflicting environment variables detected")
    time.sleep(1)
    
    debug_id = show_minimax_debug_tooltip("API key: valid, Connection: active")
    time.sleep(2)
    
    # Simulate hovering over error tooltip
    print("\n🖱️  Hovering over error tooltip...")
    tooltip_manager.show_tooltip(error_id)
    time.sleep(2)
    
    # Stop hovering - should auto-hide after delay
    print("🖱️  Stopped hovering over error tooltip")
    tooltip_manager.hide_tooltip(error_id)
    
    # Simulate hovering over debug tooltip (persistent)
    print("\n🖱️  Hovering over debug tooltip (persistent)...")
    tooltip_manager.show_tooltip(debug_id)
    time.sleep(3)
    
    # Stop hovering - debug tooltip should stay visible longer
    print("🖱️  Stopped hovering over debug tooltip")
    tooltip_manager.hide_tooltip(debug_id)
    
    # Check auto-hide
    print("\n⏰ Checking auto-hide...")
    tooltip_manager.check_auto_hide()
    
    # Show remaining tooltips
    remaining = tooltip_manager.get_all_tooltips()
    print(f"Remaining tooltips: {len(remaining)}")
    for tooltip in remaining:
        print(f"  - {tooltip.title}: {tooltip.content[:50]}...")
    
    print("\n🔍 Tooltip demo completed!")


if __name__ == "__main__":
    simulate_tooltip_hover_demo()
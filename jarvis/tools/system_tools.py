"""System date, time, and hardware diagnostic tools."""

from datetime import datetime
import psutil
from jarvis.tools.registry import registry, ToolParameter


@registry.register(
    name="get_current_time",
    description="Get the current local date, day of the week, and exact time.",
    parameters=[],
)
def get_current_time() -> str:
    """Return local date and time string."""
    now = datetime.now()
    return now.strftime("Current time is %I:%M:%S %p on %A, %B %d, %Y.")


@registry.register(
    name="get_hardware_status",
    description="Report current CPU usage, RAM utilization, and battery status.",
    parameters=[],
)
def get_hardware_status() -> str:
    """Collect CPU, RAM, and Battery statistics."""
    cpu_percent = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory()
    ram_used_gb = ram.used / (1024 ** 3)
    ram_total_gb = ram.total / (1024 ** 3)

    battery = psutil.sensors_battery()
    if battery is not None:
        charging_str = "Plugged in / Charging" if battery.power_plugged else "Discharging"
        battery_str = f"{battery.percent:.0f}% ({charging_str})"
    else:
        battery_str = "Desktop PC or AC power (no battery detected)"

    return (
        f"System Metrics:\n"
        f"- CPU Usage: {cpu_percent}%\n"
        f"- RAM: {ram.percent}% used ({ram_used_gb:.1f} GB of {ram_total_gb:.1f} GB total)\n"
        f"- Battery: {battery_str}"
    )

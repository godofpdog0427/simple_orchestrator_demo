"""ASCII art mascots for orchestrator CLI."""

from enum import Enum


class MascotPose(str, Enum):
    """Available mascot poses."""

    HAPPY = "happy"
    THINKING = "thinking"
    WAVING = "waving"
    SLEEPING = "sleeping"


class SealMascot:
    """Seal mascot with multiple poses (inspired by seal_mascot.py with Rich colors)."""

    # Seal with detailed features: body (gray), belly (white), eyes, nose, blush
    # Using Rich markup for colors
    HAPPY = """                [bright_black]██████[/bright_black]
        [bright_black]████████[/bright_black][white]██████[/white][bright_black]████[/bright_black]
      [bright_black]██[/bright_black][white]████████████████[/white][bright_black]████[/bright_black]
    [bright_black]██[/bright_black][white]██████████████████████[/white][bright_black]██[/bright_black]
   [bright_black]██[/bright_black][white]████[black]██[/black][white]██████████[black]██[/black][white]██████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]████[black]██[/black][white]██████████[black]██[/black][white]████████[/white][bright_black]██[/bright_black][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]██████████████████████████[/white][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]██[magenta]██[/magenta][white]████████████████████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]████████████████████████[/white][bright_black]██[/bright_black]
    [bright_black]████[/bright_black][white]████████████████[/white][bright_black]██████[/bright_black]
      [bright_black]████████████████████████[/bright_black]
    [bright_black]████[/bright_black]  [bright_black]████████████[/bright_black]  [bright_black]████[/bright_black]
  [bright_cyan]~~~[/bright_cyan]    [bright_cyan]~~~~~~~~~~~~[/bright_cyan]    [bright_cyan]~~~[/bright_cyan]"""

    THINKING = """                [bright_black]██████[/bright_black]
        [bright_black]████████[/bright_black][white]██████[/white][bright_black]████[/bright_black]
      [bright_black]██[/bright_black][white]████████████████[/white][bright_black]████[/bright_black]
    [bright_black]██[/bright_black][white]██████████████████████[/white][bright_black]██[/bright_black]
   [bright_black]██[/bright_black][white]████[black]██[/black][white]██████████[black]██[/black][white]██████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]████[black]██[/black][white]██████████[black]██[/black][white]████████[/white][bright_black]██[/bright_black][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]██████████████████████████[/white][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]████[/white][cyan]...[/cyan][white]████████████████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]████████████████████████[/white][bright_black]██[/bright_black]
    [bright_black]████[/bright_black][white]████████████████[/white][bright_black]██████[/bright_black]
      [bright_black]████████████████████████[/bright_black]
    [bright_black]████[/bright_black]  [bright_black]████████████[/bright_black]  [bright_black]████[/bright_black]
  [bright_cyan]~~~[/bright_cyan]    [bright_cyan]~~~~~~~~~~~~[/bright_cyan]    [bright_cyan]~~~[/bright_cyan]"""

    WAVING = """                [bright_black]██████[/bright_black]
        [bright_black]████████[/bright_black][white]██████[/white][bright_black]████[/bright_black]  [bright_cyan]~[/bright_cyan]
      [bright_black]██[/bright_black][white]████████████████[/white][bright_black]████[/bright_black]
    [bright_black]██[/bright_black][white]██████████████████████[/white][bright_black]██[/bright_black]
   [bright_black]██[/bright_black][white]████[black]██[/black][white]██████████[black]██[/black][white]██████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]████[black]██[/black][white]██████████[black]██[/black][white]████████[/white][bright_black]██[/bright_black][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]██████████████████████████[/white][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]██[magenta]██[/magenta][white]████████████████████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]████████████████████████[/white][bright_black]██[/bright_black]
    [bright_black]████[/bright_black][white]████████████████[/white][bright_black]██████[/bright_black]
      [bright_black]████████████████████████[/bright_black]
    [bright_black]████[/bright_black]  [bright_black]████████████[/bright_black]  [bright_black]████[/bright_black]
  [bright_cyan]~~~[/bright_cyan]    [bright_cyan]~~~~~~~~~~~~[/bright_cyan]    [bright_cyan]~~~[/bright_cyan]"""

    SLEEPING = """                [bright_black]██████[/bright_black]
        [bright_black]████████[/bright_black][white]██████[/white][bright_black]████[/bright_black]
      [bright_black]██[/bright_black][white]████████████████[/white][bright_black]████[/bright_black]
    [bright_black]██[/bright_black][white]██████████████████████[/white][bright_black]██[/bright_black]
   [bright_black]██[/bright_black][white]████[bright_black]-[/bright_black][white]███████████[bright_black]-[/bright_black][white]██████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]██████████████████████████[/white][bright_black]██[/bright_black][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]██████████████████████████[/white][bright_black]██[/bright_black]
  [bright_black]██[/bright_black][white]████[cyan]~~~[/cyan][white]████████████████[/white][bright_black]████[/bright_black]
   [bright_black]██[/bright_black][white]████████████████████████[/white][bright_black]██[/bright_black]
    [bright_black]████[/bright_black][white]████████████████[/white][bright_black]██████[/bright_black]
      [bright_black]████████████████████████[/bright_black]      [dim]zzz[/dim]
    [bright_black]████[/bright_black]  [bright_black]████████████[/bright_black]  [bright_black]████[/bright_black]
  [bright_cyan]~~~[/bright_cyan]    [bright_cyan]~~~~~~~~~~~~[/bright_cyan]    [bright_cyan]~~~[/bright_cyan]"""

    @classmethod
    def get_pose(cls, pose: MascotPose = MascotPose.HAPPY) -> str:
        """Get mascot ASCII art for specific pose.

        Args:
            pose: Desired mascot pose

        Returns:
            ASCII art string
        """
        pose_map = {
            MascotPose.HAPPY: cls.HAPPY,
            MascotPose.THINKING: cls.THINKING,
            MascotPose.WAVING: cls.WAVING,
            MascotPose.SLEEPING: cls.SLEEPING,
        }
        return pose_map.get(pose, cls.HAPPY)

    @classmethod
    def get_colored_pose(
        cls,
        pose: MascotPose = MascotPose.HAPPY,
        color: str = "cyan"
    ) -> str:
        """Get mascot with Rich color markup.

        Args:
            pose: Desired mascot pose
            color: Rich color tag (cyan, yellow, green, etc.) - applied as outer border color

        Returns:
            Colored ASCII art string with embedded Rich markup
        """
        # Note: The seal already has embedded Rich color markup
        # The color parameter is used for the panel border, not the seal itself
        return cls.get_pose(pose)

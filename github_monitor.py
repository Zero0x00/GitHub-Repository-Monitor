#!/usr/bin/env python3
"""
GitHub Repository Monitor & Report
- Tracks changes in GitHub organization repositories
- Detects added and removed repositories
- Reports changes with beautiful terminal output
- Optional Slack notifications
"""

import argparse
import configparser
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import requests
from colorama import Fore, Style, init
from rich.console import Console
from rich.table import Table

# Initialize colorama
init(autoreset=True)

# Initialize Rich console
console = Console()


class GitHubMonitor:
    """GitHub Repository Monitor for tracking repository changes within an organization."""

    def __init__(self):
        """Initialize the GitHubMonitor with default settings."""
        self.config_dir = Path.home() / ".config" / "github-monitor"
        self.config_file = self.config_dir / "config.ini"
        self.config = configparser.ConfigParser()
        
        # Default configuration
        self.organization = ""
        self.github_token = ""
        self.slack_webhook_url = ""
        self.enable_slack = False
        
        # File paths
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.repo_list_file = f"repo-list-{self.today}"
        self.added_repos_file = f"added-repos-{self.today}"
        self.deleted_repos_file = f"deleted-repos-{self.today}"
        self.backup_dir = f"backups_{self.today}"
        self.log_file = "github-monitor.log"
        
        # Load configuration if exists
        self.load_config()
        
        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Set up logging to file and console."""
        self.log_info("GitHub Repository Monitor initialized")

    def log(self, level: str, message: str):
        """Log a message with timestamp to file and console.
        
        Args:
            level: Log level (INFO, WARNING, ERROR)
            message: Message to log
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format for console output with color
        if level == "INFO":
            console_msg = f"{Fore.GREEN}[{timestamp}] [{level}] {message}{Style.RESET_ALL}"
        elif level == "WARNING":
            console_msg = f"{Fore.YELLOW}[{timestamp}] [{level}] {message}{Style.RESET_ALL}"
        elif level == "ERROR":
            console_msg = f"{Fore.RED}[{timestamp}] [{level}] {message}{Style.RESET_ALL}"
        else:
            console_msg = f"{Fore.WHITE}[{timestamp}] [{level}] {message}{Style.RESET_ALL}"
        
        # Print to console
        print(console_msg)
        
        # Log to file (without colors)
        file_msg = f"[{timestamp}] [{level}] {message}"
        with open(self.log_file, "a") as f:
            f.write(file_msg + "\n")

    def log_info(self, message: str):
        """Log an info message."""
        self.log("INFO", message)

    def log_warning(self, message: str):
        """Log a warning message."""
        self.log("WARNING", message)

    def log_error(self, message: str):
        """Log an error message."""
        self.log("ERROR", message)

    def load_config(self):
        """Load configuration from config file."""
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create a new one
        if self.config_file.exists():
            self.config.read(self.config_file)
            
            # Get values from config
            if "Settings" in self.config:
                self.organization = self.config.get("Settings", "organization", fallback="")
                self.github_token = self.config.get("Settings", "github_token", fallback="")
                self.slack_webhook_url = self.config.get("Settings", "slack_webhook_url", fallback="")
                self.enable_slack = self.config.getboolean("Settings", "enable_slack", fallback=False)
        else:
            # Initialize with empty config
            self.config["Settings"] = {
                "organization": "",
                "github_token": "",
                "slack_webhook_url": "",
                "enable_slack": "False"
            }
            self.save_config()

    def save_config(self):
        """Save current configuration to config file."""
        self.config["Settings"] = {
            "organization": self.organization,
            "github_token": self.github_token,
            "slack_webhook_url": self.slack_webhook_url,
            "enable_slack": str(self.enable_slack)
        }
        
        with open(self.config_file, "w") as configfile:
            self.config.write(configfile)
        
        # Set permissions to restrict access (equivalent to chmod 600)
        os.chmod(self.config_file, 0o600)

    def update_config(self, organization: str = None, github_token: str = None, 
                     slack_webhook_url: str = None, enable_slack: bool = None):
        """Update configuration with new values.
        
        Args:
            organization: GitHub organization name
            github_token: GitHub API token
            slack_webhook_url: Slack webhook URL for notifications
            enable_slack: Whether to enable Slack notifications
        """
        if organization is not None:
            self.organization = organization
        
        if github_token is not None:
            self.github_token = github_token
        
        if slack_webhook_url is not None:
            self.slack_webhook_url = slack_webhook_url
        
        if enable_slack is not None:
            self.enable_slack = enable_slack
        
        self.save_config()
        self.log_info("Configuration updated successfully")

    def show_config(self):
        """Display current configuration."""
        console.print("\n[bold]Current Configuration:[/bold]")
        
        table = Table(show_header=True, header_style="bold")
        table.add_column("Setting")
        table.add_column("Value")
        
        table.add_row("Organization", self.organization or "[italic]Not set[/italic]")
        
        # Mask token for security
        token_display = "********" if self.github_token else "[italic]Not set[/italic]"
        table.add_row("GitHub Token", token_display)
        
        # Mask webhook URL for security
        webhook_display = "********" if self.slack_webhook_url else "[italic]Not set[/italic]"
        table.add_row("Slack Webhook URL", webhook_display)
        
        table.add_row("Slack Notifications", "Enabled" if self.enable_slack else "Disabled")
        table.add_row("Config File", str(self.config_file))
        
        console.print(table)
        console.print()

    def validate_token(self) -> bool:
        """Validate GitHub token by making a test API call.
        
        Returns:
            bool: True if token is valid, False otherwise
        """
        if not self.github_token:
            self.log_warning("No GitHub token provided")
            return False
            
        headers = self._get_auth_headers()
        try:
            response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
            if response.status_code == 200:
                self.log_info("GitHub token validated successfully")
                return True
            else:
                self.log_error(f"GitHub token validation failed: {response.json().get('message', 'Unknown error')}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_error(f"Error validating GitHub token: {e}")
            return False

    def validate_organization(self) -> bool:
        """Validate organization by making a test API call.
        
        Returns:
            bool: True if organization exists, False otherwise
        """
        if not self.organization:
            self.log_error("No organization name provided")
            return False
            
        headers = self._get_auth_headers()
        try:
            response = requests.get(
                f"https://api.github.com/orgs/{self.organization}", 
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                self.log_info(f"Organization '{self.organization}' validated successfully")
                return True
            else:
                self.log_error(f"Organization validation failed: {response.json().get('message', 'Unknown error')}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_error(f"Error validating organization: {e}")
            return False

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for GitHub API.
        
        Returns:
            Dict containing the appropriate headers
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Repository-Monitor"
        }
        
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
            
        return headers

    def backup_files(self):
        """Backup existing files to a backup directory."""
        self.log_info("Backing up existing files")
        
        # Create backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Files to backup
        files = [self.repo_list_file, self.added_repos_file, self.deleted_repos_file]
        
        for file in files:
            if os.path.exists(file):
                backup_path = os.path.join(self.backup_dir, f"old_{file}")
                self.log_info(f"Backing up {file} to {backup_path}")
                
                # Copy and remove original
                with open(file, "r") as src, open(backup_path, "w") as dst:
                    dst.write(src.read())
                    
                os.remove(file)

    def fetch_repositories(self) -> List[str]:
        """Fetch all repositories for the organization from GitHub API.
        
        Returns:
            List of repository full names (org/repo)
        """
        self.log_info(f"Fetching repositories for {self.organization}")
        
        if not self.organization:
            self.log_error("No organization name provided")
            return []
            
        headers = self._get_auth_headers()
        
        if not self.github_token:
            self.log_warning("GitHub token not provided. API rate limits may apply.")
        
        repositories = []
        page = 1
        total_repos = 0
        
        # Use session for connection pooling
        with requests.Session() as session:
            while True:
                try:
                    # Make API call with timeout and retry logic
                    for attempt in range(3):  # Retry up to 3 times
                        try:
                            response = session.get(
                                f"https://api.github.com/orgs/{self.organization}/repos",
                                params={"type": "all", "per_page": 100, "page": page},
                                headers=headers,
                                timeout=30
                            )
                            response.raise_for_status()
                            break
                        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
                            if attempt == 2:  # Last attempt
                                raise
                            self.log_warning(f"API call failed (attempt {attempt+1}): {e}. Retrying...")
                            time.sleep(2)  # Wait before retry
                    
                    # Parse response
                    repos_data = response.json()
                    
                    # Check if we got an empty list or not a list at all
                    if not isinstance(repos_data, list) or not repos_data:
                        break
                        
                    # Extract repository names
                    page_repos = [repo["full_name"] for repo in repos_data]
                    repositories.extend(page_repos)
                    
                    count = len(page_repos)
                    total_repos += count
                    
                    self.log_info(f"Retrieved {count} repositories on page {page} (total: {total_repos})")
                    
                    # Check if we got less than the maximum per page, which means we're done
                    if count < 100:
                        break
                        
                    page += 1
                    
                except Exception as e:
                    self.log_error(f"Error fetching repositories: {e}")
                    break
        
        # Sort the repository list for efficient comparison
        repositories.sort()
        
        # Save repositories to file
        self._save_list_to_file(repositories, self.repo_list_file)
        
        self.log_info(f"Successfully fetched {total_repos} repositories")
        return repositories

    def _save_list_to_file(self, items: List[str], filename: str):
        """Save a list of items to a file, one item per line.
        
        Args:
            items: List of strings to save
            filename: Name of the file to save to
        """
        with open(filename, "w") as f:
            for item in items:
                f.write(f"{item}\n")

    def find_previous_list(self) -> Optional[str]:
        """Find the most recent previous repository list.
        
        Returns:
            Filename of the most recent previous repository list or None if not found
        """
        # List all repo-list-* files
        files = [f for f in os.listdir(".") if f.startswith("repo-list-") and f != self.repo_list_file]
        
        if not files:
            self.log_warning("No previous repository list found")
            return None
            
        # Sort by modification time, newest first
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        
        previous_list = files[0]
        return previous_list

    def compare_repositories(self, current_list: List[str], previous_list: List[str]) -> Tuple[List[str], List[str]]:
        """Compare current and previous repository lists to detect changes.
        
        Args:
            current_list: Current list of repositories
            previous_list: Previous list of repositories
            
        Returns:
            Tuple of (added_repos, deleted_repos)
        """
        self.log_info("Comparing current list with previous list")
        
        # Find added repositories (in current but not in previous)
        added_repos = [repo for repo in current_list if repo not in previous_list]
        
        # Find deleted repositories (in previous but not in current)
        deleted_repos = [repo for repo in previous_list if repo not in current_list]
        
        # Save to files
        self._save_list_to_file(added_repos, self.added_repos_file)
        self._save_list_to_file(deleted_repos, self.deleted_repos_file)
        
        self.log_info(f"Found {len(added_repos)} new repositories and {len(deleted_repos)} deleted repositories")
        
        return added_repos, deleted_repos

    def print_header(self, title: str):
        """Print a styled header.
        
        Args:
            title: Header title
        """
        width = 80
        padding = (width - len(title) - 2) // 2
        
        console.print()
        console.print("=" * width, style="bold")
        console.print(f"{' ' * padding}{title}{' ' * padding}", style="bold")
        console.print("=" * width, style="bold")
        console.print()

    def print_table(self, items: List[str], title: str):
        """Print a styled table of items.
        
        Args:
            items: List of items to display
            title: Table title
        """
        count = len(items)
        
        # Print title and border
        console.print(f"\n[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]")
        console.print(f"[bold]{title}[/bold]")
        console.print(f"[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]")
        
        # Print count
        console.print(f"[cyan]Total count: {count}[/cyan]")
        
        # Print data
        if count == 0:
            console.print("[yellow]No entries found[/yellow]")
        elif count < 20:
            for item in items:
                # Truncate long items
                if len(item) > 70:
                    display_item = item[:70] + "..."
                else:
                    display_item = item
                console.print(f"[blue]• {display_item}[/blue]")
        else:
            console.print(f"[yellow]Too many items to display ({count} repositories)[/yellow]")
            console.print("[yellow]Results saved to file[/yellow]")
        
        console.print(f"[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]\n")

    def send_slack_notification(self, added_repos: List[str], deleted_repos: List[str]) -> bool:
        """Send notification to Slack with repository changes.
        
        Args:
            added_repos: List of added repositories
            deleted_repos: List of deleted repositories
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.enable_slack or not self.slack_webhook_url:
            return True
            
        self.log_info("Sending notification to Slack")
        
        added_count = len(added_repos)
        deleted_count = len(deleted_repos)
        
        # Format repositories for Slack
        added_list = "\n".join(f"• {repo}" for repo in added_repos) if added_repos else "None"
        deleted_list = "\n".join(f"• {repo}" for repo in deleted_repos) if deleted_repos else "None"
        
        # Set color based on changes
        color = "#ff9800" if added_count > 0 or deleted_count > 0 else "#36a64f"
        
        # Create payload
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"GitHub Repository Change Report for {self.organization}",
                    "text": f"Changes detected on {self.today}",
                    "fields": [
                        {
                            "title": f"Added Repositories ({added_count})",
                            "value": added_list,
                            "short": False
                        },
                        {
                            "title": f"Deleted Repositories ({deleted_count})",
                            "value": deleted_list,
                            "short": False
                        }
                    ],
                    "footer": "GitHub Repository Monitor",
                    "ts": int(time.time())
                }
            ]
        }
        
        try:
            # Send notification
            response = requests.post(
                self.slack_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            
            self.log_info("Slack notification sent successfully")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to send Slack notification: {e}")
            return False

    def run(self):
        """Run the GitHub repository monitor."""
        # Validate settings
        if not self.organization:
            self.log_error("Organization name is not set. Use --org to set it.")
            return False
            
        # Validate GitHub token if provided
        if self.github_token and not self.validate_token():
            self.log_error("Invalid GitHub token. Please check your token and try again.")
            return False
            
        # Validate organization
        if not self.validate_organization():
            self.log_error(f"Invalid organization: {self.organization}. Please check the name and try again.")
            return False
            
        # Print welcome message
        self.print_header("GitHub Repository Monitor")
        self.log_info(f"Starting repository monitoring for {self.organization}")
        
        # Backup existing files
        self.backup_files()
        
        # Fetch current repository list
        current_repos = self.fetch_repositories()
        if not current_repos:
            self.log_error("Failed to fetch repositories")
            return False
            
        # Find previous repository list
        previous_list_file = self.find_previous_list()
        
        if previous_list_file:
            # Load previous repositories
            with open(previous_list_file, 'r') as f:
                previous_repos = [line.strip() for line in f if line.strip()]
                
            previous_date = previous_list_file.replace("repo-list-", "")
            self.log_info(f"Using previous list from {previous_date} for comparison")
            
            # Compare repositories
            added_repos, deleted_repos = self.compare_repositories(current_repos, previous_repos)
            
            # Print results
            self.print_header("Repository Changes Report")
            self.print_table(added_repos, "Added Repositories")
            self.print_table(deleted_repos, "Deleted Repositories")
            
            # Send Slack notification if enabled
            if self.enable_slack:
                self.send_slack_notification(added_repos, deleted_repos)
                
        else:
            self.log_info("No previous repository list found. This is the first run.")
            self.print_header("Initial Repository Report")
            self.print_table(current_repos, "Current Repositories")
            
        # Print summary
        self.print_header("Summary")
        if previous_list_file:
            previous_date = previous_list_file.replace("repo-list-", "")
            with open(previous_list_file, 'r') as f:
                previous_repos = [line.strip() for line in f if line.strip()]
            self.print_table(previous_repos, f"Previous Repository List ({previous_date})")
            
        self.print_table(current_repos, f"Current Repository List ({self.today})")
        
        self.log_info("Script completed successfully")
        return True


def parse_arguments():
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="GitHub Repository Monitor")
    
    parser.add_argument("-o", "--org", dest="organization", 
                        help="Set GitHub organization name")
    
    parser.add_argument("-t", "--token", dest="github_token",
                        help="Set GitHub API token")
    
    parser.add_argument("-s", "--slack", dest="slack_webhook_url",
                        help="Enable Slack notifications with webhook URL")
    
    parser.add_argument("--enable-slack", dest="enable_slack", action="store_true",
                        help="Enable Slack notifications using stored webhook URL")
    
    parser.add_argument("--show-config", dest="show_config", action="store_true",
                        help="Show current configuration")
    
    parser.add_argument("-d", "--dry-run", dest="dry_run", action="store_true",
                        help="Run without making changes (for testing)")
    
    return parser.parse_args()


def main():
    """Main function."""
    # Initialize the monitor
    monitor = GitHubMonitor()
    
    # Parse arguments
    args = parse_arguments()
    
    # Update configuration if arguments provided
    if args.organization or args.github_token or args.slack_webhook_url or args.enable_slack:
        monitor.update_config(
            organization=args.organization,
            github_token=args.github_token,
            slack_webhook_url=args.slack_webhook_url,
            enable_slack=args.enable_slack if args.enable_slack is not None else 
                         (True if args.slack_webhook_url else None)
        )
    
    # Show configuration if requested
    if args.show_config:
        monitor.show_config()
        return 0
        
    # Check if we have enough configuration to run
    if not monitor.organization:
        console.print("[red]Error:[/red] Organization name is required. Use --org to set it or check the configuration.")
        monitor.show_config()
        return 1
        
    # Run the monitor (skip if dry run)
    if not args.dry_run:
        success = monitor.run()
        return 0 if success else 1
    else:
        console.print("[yellow]Dry run mode:[/yellow] No changes will be made.")
        monitor.show_config()
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation canceled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""
GitHub Monitor Configuration Utility
- Set up and configure GitHub Monitor settings
- Securely store GitHub token and organization settings
"""

import argparse
import configparser
import os
import sys
from pathlib import Path

import requests
from rich.console import Console

console = Console()


def create_config_directory():
    """Create configuration directory if it doesn't exist."""
    config_dir = Path.home() / ".config" / "github-monitor"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def load_existing_config():
    """Load existing configuration or create new one."""
    config_dir = create_config_directory()
    config_file = config_dir / "config.ini"
    
    config = configparser.ConfigParser()
    
    if config_file.exists():
        config.read(config_file)
        console.print("[green]Loaded existing configuration[/green]")
    else:
        config["Settings"] = {
            "organization": "",
            "github_token": "",
            "slack_webhook_url": "",
            "enable_slack": "False"
        }
        console.print("[yellow]No existing configuration found, creating new[/yellow]")
    
    return config, config_file


def validate_github_token(token):
    """Validate GitHub token by making a test API call."""
    if not token:
        return False
        
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Repository-Monitor"
    }
    
    try:
        response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if response.status_code == 200:
            username = response.json().get('login')
            console.print(f"[green]✓ Token valid! Authenticated as: {username}[/green]")
            return True
        else:
            error_msg = response.json().get('message', 'Unknown error')
            console.print(f"[red]✗ Token validation failed: {error_msg}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error validating token: {e}[/red]")
        return False


def validate_organization(token, org_name):
    """Validate organization by making a test API call."""
    if not org_name:
        return False
        
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Repository-Monitor"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
    
    try:
        response = requests.get(
            f"https://api.github.com/orgs/{org_name}", 
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            console.print(f"[green]✓ Organization '{org_name}' exists and is accessible[/green]")
            return True
        else:
            error_msg = response.json().get('message', 'Unknown error')
            console.print(f"[red]✗ Organization validation failed: {error_msg}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error validating organization: {e}[/red]")
        return False


def setup_configuration(args):
    """Set up configuration from command-line arguments."""
    console.print("[bold]GitHub Repository Monitor Configuration[/bold]")
    
    config, config_file = load_existing_config()
    
    # Get current values
    current_org = config.get("Settings", "organization", fallback="")
    current_token = config.get("Settings", "github_token", fallback="")
    current_slack_url = config.get("Settings", "slack_webhook_url", fallback="")
    current_enable_slack = config.getboolean("Settings", "enable_slack", fallback=False)
    
    # Update token if provided
    if args.token:
        console.print("[bold]GitHub Token Configuration[/bold]")
        token = args.token
        if validate_github_token(token):
            config["Settings"]["github_token"] = token
            console.print("[green]GitHub token updated and validated successfully[/green]")
        else:
            console.print("[yellow]Token validation failed, but saving anyway[/yellow]")
            config["Settings"]["github_token"] = token
    elif current_token:
        console.print("[bold]GitHub Token Configuration[/bold]")
        console.print(f"Current token: {'*' * 8}{current_token[-4:] if len(current_token) > 4 else ''}")
        console.print("Validating existing token...")
        validate_github_token(current_token)
    else:
        console.print("[yellow]No GitHub token set. Please provide one with --token[/yellow]")
    
    # Update organization if provided
    if args.org:
        console.print("[bold]GitHub Organization Configuration[/bold]")
        org_name = args.org
        token = config.get("Settings", "github_token", fallback="")
        if token and validate_organization(token, org_name):
            config["Settings"]["organization"] = org_name
            console.print(f"[green]Organization '{org_name}' validated and saved[/green]")
        else:
            console.print(f"[yellow]Organization '{org_name}' could not be validated, but saving anyway[/yellow]")
            config["Settings"]["organization"] = org_name
    elif current_org:
        console.print("[bold]GitHub Organization Configuration[/bold]")
        console.print(f"Current organization: {current_org}")
        if config.get("Settings", "github_token", fallback=""):
            console.print("Validating existing organization...")
            validate_organization(config["Settings"]["github_token"], current_org)
    else:
        console.print("[yellow]No organization set. Please provide one with --org[/yellow]")
    
    # Update Slack settings if provided
    if args.slack:
        console.print("[bold]Slack Notifications Configuration[/bold]")
        config["Settings"]["slack_webhook_url"] = args.slack
        config["Settings"]["enable_slack"] = "True"
        console.print("[green]Slack webhook URL saved and notifications enabled[/green]")
    elif args.enable_slack is not None:
        console.print("[bold]Slack Notifications Configuration[/bold]")
        if current_slack_url:
            config["Settings"]["enable_slack"] = str(args.enable_slack)
            status = "enabled" if args.enable_slack else "disabled"
            console.print(f"[green]Slack notifications {status}[/green]")
        else:
            console.print("[yellow]Cannot enable Slack notifications without a webhook URL[/yellow]")
    elif current_slack_url:
        console.print("[bold]Slack Notifications Configuration[/bold]")
        console.print(f"Current Slack webhook URL: {'*' * 20}{current_slack_url[-8:] if len(current_slack_url) > 8 else ''}")
        console.print(f"Slack notifications: {'Enabled' if current_enable_slack else 'Disabled'}")
    
    # Save configuration
    with open(config_file, "w") as configfile:
        config.write(configfile)
    
    # Set restrictive permissions (equivalent to chmod 600)
    os.chmod(config_file, 0o600)
    
    console.print(f"[green]✓ Configuration saved to {config_file}[/green]")
    
    # Show final configuration
    console.print("\n[bold]Configuration Summary:[/bold]")
    console.print(f"Organization: {config.get('Settings', 'organization', fallback='Not set')}")
    console.print(f"GitHub token: {'*' * 8}{config.get('Settings', 'github_token', fallback='Not set')[-4:] if len(config.get('Settings', 'github_token', fallback='')) > 4 else 'Not set'}")
    slack_url = config.get('Settings', 'slack_webhook_url', fallback='')
    console.print(f"Slack webhook: {'*' * 20}{slack_url[-8:] if len(slack_url) > 8 else 'Not set'}")
    console.print(f"Slack notifications: {'Enabled' if config.getboolean('Settings', 'enable_slack', fallback=False) else 'Disabled'}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="GitHub Repository Monitor Configuration")
    
    parser.add_argument("--token", dest="token", help="GitHub API token")
    parser.add_argument("--org", dest="org", help="GitHub organization name")
    parser.add_argument("--slack", dest="slack", help="Slack webhook URL")
    parser.add_argument("--enable-slack", dest="enable_slack", action="store_true", 
                      help="Enable Slack notifications using the stored webhook URL")
    parser.add_argument("--disable-slack", dest="enable_slack", action="store_false", 
                      help="Disable Slack notifications")
    parser.set_defaults(enable_slack=None)
    
    return parser.parse_args()

if __name__ == "__main__":
    try:
        args = parse_arguments()
        setup_configuration(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error during configuration: {e}[/red]")
        sys.exit(1)

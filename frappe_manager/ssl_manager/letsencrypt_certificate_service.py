import shlex
from io import StringIO
from pathlib import Path
from typing import List, Literal, Tuple
from certbot._internal.main import make_or_verify_needed_dirs
from certbot._internal.plugins import disco as plugins_disco
from certbot._internal import cli, storage
from certbot._internal.display import obj as display_obj
from certbot import crypto_util
from certbot.errors import AuthorizationError
from frappe_manager.logger import log
from frappe_manager.ssl_manager import SUPPORTED_SSL_TYPES
from frappe_manager.ssl_manager.certificate_exceptions import (
    SSLCertificateChallengeFailed,
    SSLCertificateGenerateFailed,
    SSLCertificateNotFoundError,
)
from frappe_manager.ssl_manager.letsencrypt_certificate import LetsencryptSSLCertificate
from frappe_manager.ssl_manager.ssl_certificate_service import SSLCertificateService
from frappe_manager.display_manager.DisplayManager import richprint


class LetsEncryptCertificateService(SSLCertificateService):
    def __init__(
        self,
        ssl_service_dir: Path,
        webroot_dir: Path,
        preferred_challenge: Literal['http', 'dns'] = 'http',
    ):
        self.webroot_dir = webroot_dir
        self.preferred_challenge = preferred_challenge
        self.root_dir = ssl_service_dir / SUPPORTED_SSL_TYPES.le.value

        # certbot dirs
        self.config_dir: Path = self.root_dir / "config"
        self.work_dir: Path = self.root_dir / 'work'
        self.logs_dir: Path = self.root_dir / 'logs'

        self.base_command = f"--work-dir {self.work_dir} --config-dir {self.config_dir} --logs-dir {self.logs_dir}"
        self.console_output = StringIO()

    def renew_certificate(self, certificate: LetsencryptSSLCertificate):
        renew_certificate_command = (
            self.base_command + f' renew --cert-name {certificate.domain} --non-interactive --force-renewal'
        )
        renew_certificate_config = self._get_le_config(shlex.split(renew_certificate_command), quiet=True)
        make_or_verify_needed_dirs(renew_certificate_config)
        plugins = plugins_disco.PluginsRegistry.find_all()
        renew_certificate_config.func(renew_certificate_config, plugins)

    def _get_le_config(self, cli_args: List[str], quiet: bool = False):
        plugins = plugins_disco.PluginsRegistry.find_all()

        config = cli.prepare_and_parse_args(plugins, cli_args)
        if quiet:
            config.quiet = True
            config.noninteractive_mode = True
            displayer = display_obj.NoninteractiveDisplay(outfile=self.console_output)
            display_obj.set_display(displayer)
        return config

    def get_certificate_paths(self, certificate: LetsencryptSSLCertificate) -> Tuple[Path, Path]:
        config = self._get_le_config(shlex.split(self.base_command), quiet=True)
        for renewal_file in storage.renewal_conf_files(config):
            renewal_candidate = storage.RenewableCert(renewal_file, config)
            crypto_util.verify_renewable_cert(renewal_candidate)

            # parsed_certs.append(renewal_candidate)
            if certificate.domain == renewal_candidate.lineagename:
                privkey_path = Path(renewal_candidate.key_path)
                fullchain_path = Path(renewal_candidate.fullchain_path)
                return privkey_path, fullchain_path
        raise SSLCertificateNotFoundError(certificate.domain)

    def remove_certificate(self, certificate: LetsencryptSSLCertificate):
        richprint.change_head("Removing Letsencrypt certificate")
        remove_certificate_command = self.base_command + f' delete --cert-name {certificate.domain}'
        remove_certificate_config = self._get_le_config(shlex.split(remove_certificate_command), quiet=True)
        plugins = plugins_disco.PluginsRegistry.find_all()
        remove_certificate_config.func(remove_certificate_config, plugins)
        richprint.print("Removed Letsencrypt certificate")

    def generate_certificate(self, certificate: LetsencryptSSLCertificate):
        gen_command: str = self.base_command + f" certonly --webroot -w {self.webroot_dir} "
        gen_command += f' --keep-until-expiring --expand'
        # gen_command += ' --staging'
        gen_command += f' --agree-tos -m "{certificate.email}" --no-eff-email'

        all_domains = [f'{certificate.domain}'] + certificate.alias_domains

        # alias domains
        for alias_domain in all_domains:
            gen_command += f" -d '{alias_domain}'"

        try:
            richprint.change_head("Getting Letsencrypt certificate")
            config = self._get_le_config(shlex.split(gen_command), quiet=True)
            plugins = plugins_disco.PluginsRegistry.find_all()
            config.func(config, plugins)
            richprint.stdout.print(self.console_output.getvalue().strip())

        except AuthorizationError as e:
            logger = log.get_logger()
            logger.exception(e)
            richprint.stdout.print(self.console_output.getvalue().strip())
            raise SSLCertificateChallengeFailed(self.preferred_challenge)

        except Exception as e:
            logger = log.get_logger()
            logger.exception(e)
            richprint.stdout.print(self.console_output.getvalue().strip())
            raise SSLCertificateGenerateFailed()

        richprint.print("Acquired Letsencrypt certificate: Done")
        return self.get_certificate_paths(certificate)

# Politique de sécurité

## Signaler une vulnérabilité

Ne **pas** ouvrir d'issue publique pour une faille de sécurité.

- Utiliser **GitHub Security Advisories** (onglet *Security → Report a vulnerability*), ou
- contacter le mainteneur en privé.

Délai de réponse visé : sous 5 jours ouvrés.

## Périmètre

Ce dépôt est un **POC**. Éléments sensibles à considérer avant tout déploiement réel :

- **Données personnelles** — une plaque d'immatriculation est une donnée à caractère
  personnel (RGPD). Voir [docs/RISQUES.md § R5](docs/RISQUES.md#r5--conformité-rgpd).
- **Flux caméra / RTSP** — identifiants, chiffrement du transport, cloisonnement réseau.
- **Snapshots** — contiennent des plaques ; chiffrement au repos, rétention minimale.
- **Sorties d'événements** — contrôle d'accès aux fichiers/API en aval.

## Contrôles automatisés en place (CI)

| Contrôle | Outil | Job |
|----------|-------|-----|
| Licences (aucune AGPL / GPL fort) | `pip-licenses` + `scripts/check_licenses.sh` | `licenses` |
| Vulnérabilités des dépendances (CVE) | `pip-audit` (base PyPA) | `security` |
| Cohérence des dépendances | `pip check` | `security` |
| Analyse statique (SAST) | CodeQL (`security-and-quality`) | `codeql.yml` |
| Mises à jour de sécurité | Dependabot (pip + github-actions) | `dependabot.yml` |
| Moindre privilège | `permissions: contents: read` + `persist-credentials: false` | tous |

## Durcissement restant (voir docs/RISQUES.md § R11, R14)

- Épingler les actions GitHub sur **SHA de commit** (Dependabot proposera les bumps).
- Passer `pip-audit` **bloquant** (retirer `continue-on-error`) avant mise en service.
- Faire **échouer** le contrôle de licences sur les licences `UNKNOWN`.
- Ajouter un **scan de secrets** (gitleaks/trufflehog) et la *push protection* GitHub.
- Envisager `step-security/harden-runner` (politique d'egress) sur les jobs.

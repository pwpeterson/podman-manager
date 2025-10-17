# Security Standards

These security rules apply across all Roo modes and must be followed regardless of the specific task.

## Code Security Requirements

**MUST** never suggest or implement code that contains obvious security vulnerabilities

**MUST** always validate and sanitize user inputs in any code examples

**MUST** use parameterized queries instead of string concatenation for database operations

**MUST** avoid hardcoding secrets, API keys, passwords, or sensitive configuration

**MUST** use secure defaults in all code recommendations

**MUST** implement proper error handling that doesn't expose sensitive information

## Authentication & Authorization

**MUST** implement proper authentication checks before accessing protected resources

**MUST** use established authentication libraries rather than rolling custom solutions

**MUST** implement proper session management and timeout handling

**MUST** follow principle of least privilege in access control recommendations

## Data Protection

**MUST** encrypt sensitive data at rest and in transit

**MUST** use secure hashing algorithms (bcrypt, Argon2) for password storage

**MUST** implement proper data validation and sanitization

**MUST** avoid logging sensitive information (passwords, tokens, personal data)

## Dependency Security

**MUST** recommend using dependency scanning tools

**MUST** suggest keeping dependencies up to date

**MUST** warn about known vulnerable packages when encountered

**SHOULD** recommend using lock files for dependency management

## Communication Security

**MUST** recommend HTTPS for all web communications

**MUST** suggest proper certificate validation

**MUST** recommend secure communication protocols

**MUST** warn against transmitting sensitive data in URLs or logs

## Configuration Security

**MUST** recommend secure configuration practices

**MUST** suggest using environment variables for sensitive configuration

**MUST** recommend proper file permissions for configuration files

**MUST** warn against default credentials or configurations

## Security Review Process

**MUST** consider security implications in all code recommendations

**MUST** flag potential security issues when reviewing code

**MUST** provide security-focused alternatives when suggesting improvements

**MUST** educate users about security best practices when relevant

## Incident Response

**MUST** recommend proper logging and monitoring for security events

**MUST** suggest implementing security incident response procedures

**MUST** recommend regular security audits and penetration testing

## Compliance Considerations

**SHOULD** consider relevant compliance requirements (GDPR, HIPAA, PCI-DSS)

**SHOULD** recommend data retention and deletion policies

**SHOULD** suggest privacy-by-design principles

**NOTE**: When in doubt about security implications, err on the side of caution and recommend consulting with security experts.

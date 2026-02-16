# Contributing to Standard MeshPack

Thank you for your interest in contributing to the MeshPack specification! This document provides guidelines and workflows for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Workflow](#development-workflow)
- [Reporting Issues](#reporting-issues)
- [Submitting Changes](#submitting-changes)
- [Style Guidelines](#style-guidelines)

## Code of Conduct

This project adheres to the Contributor Covenant Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the issue
- **Expected vs actual behavior**
- **Version information** (format version, SDK version)
- **Sample files** if applicable

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- Use a clear, descriptive title
- Provide detailed explanation of the proposed functionality
- Include examples or use cases
- Explain why this enhancement would be useful

### Contributing to the Specification

Contributions to the format specification (in `definition/README.md`) should:

1. Be backwards-compatible whenever possible
2. Include rationale for the change
3. Update JSON schemas accordingly
4. Consider impact on all three SDK implementations

## Development Workflow

### Prerequisites

- **Python 3.10+** (for SDK generators)
- **Node.js 18+** (for TypeScript SDK)
- **Rust 1.70+** (for Rust SDK)
- **Just** command runner ([installation guide](https://github.com/casey/just))

Install Python dependencies:
```bash
pip install -r requirements.txt
```

### The Schema-Driven Architecture

**IMPORTANT**: This repository uses a **contract-first, schema-driven** approach:

```
JSON Schemas (source of truth)
    ↓
Python Generator (generate_sdks.py)
    ↓
Auto-generated SDKs (Python, Rust, TypeScript)
```

**Never edit generated code directly!** All changes must flow through schemas and templates.

### Making Changes

#### 1. Modifying the Specification

Edit `definition/README.md` to update the human-readable specification.

#### 2. Updating Schemas

Edit JSON Schema files in `schema/`:
- `manifest.schema.json` - Root manifest structure
- `shard.schema.json` - Index shard and file entry definitions
- `sidecar.schema.json` - Detached integrity sidecar
- `common.schema.json` - Shared type definitions (canonical reference)

After editing, validate:
```bash
just validate
```

#### 3. Updating Generators

If you need to change how SDKs are generated:

- **Logic changes**: Edit `generators/generate_sdks.py`
- **Template changes**: Edit files in `generators/templates/{python,rust,typescript}/`

#### 4. Regenerate SDKs

After any schema or template change:
```bash
just generate
```

#### 5. Compile and Test

Build the generated SDKs:
```bash
just compile
```

This will:
- Build Python wheel package
- Compile Rust crate
- Compile TypeScript package

### Full Workflow Example

```bash
# 1. Create a feature branch
git checkout -b feature/add-compression-metadata

# 2. Edit the specification
vim definition/README.md

# 3. Update schemas to reflect changes
vim schema/manifest.schema.json

# 4. Regenerate SDKs
just generate

# 5. Validate schemas
just validate

# 6. Compile all SDKs
just compile

# 7. Test manually (until automated tests exist)
# Create a sample .meshpack, verify it works

# 8. Commit changes (schemas + templates + docs, NOT generated/)
git add schema/ definition/ generators/
git commit -m "feat: add compression metadata to manifest"

# 9. Push and create PR
git push origin feature/add-compression-metadata
```

## Reporting Issues

### Issue Labels

- `bug` - Something isn't working
- `enhancement` - New feature request
- `documentation` - Improvements to docs
- `specification` - Changes to format spec
- `generator` - Issues with SDK generation
- `good first issue` - Good for newcomers

## Submitting Changes

### Pull Request Process

1. **Fork** the repository
2. **Create a feature branch** from `master`
3. **Make your changes** following the workflow above
4. **Test thoroughly**:
   - Schemas validate (`just validate`)
   - SDKs compile (`just compile`)
   - Generated code works as expected
5. **Write clear commit messages** (see conventions below)
6. **Update documentation** if needed
7. **Submit a pull request**

### PR Checklist

Before submitting, ensure:

- [ ] Schemas validate successfully
- [ ] All three SDKs compile without errors
- [ ] Documentation is updated (if applicable)
- [ ] Commit messages follow conventions
- [ ] No generated files are committed (check `.gitignore`)
- [ ] Examples/samples are updated (if format changed)

### Commit Message Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding tests
- `chore`: Updating build tasks, etc.

**Scopes**:
- `schema`: JSON schema changes
- `generator`: SDK generation logic
- `spec`: Format specification
- `python`: Python SDK specific
- `rust`: Rust SDK specific
- `typescript`: TypeScript SDK specific

**Examples**:
```
feat(schema): add optional compression_method field to manifest

fix(generator): correct handling of optional nested objects

docs(spec): clarify resource_ref naming convention

chore(ci): add automated SDK compilation test
```

## Style Guidelines

### JSON Schema

- Use descriptive `description` fields
- Include `examples` where helpful
- Prefer explicit over implicit (always specify `required`)
- Use semantic versioning for `format_version`

### Python Code

- Follow PEP 8
- Use type hints
- Docstrings for all public functions

### Rust Code

- Follow `rustfmt` defaults
- Use `clippy` for linting
- Document public APIs with doc comments

### TypeScript Code

- Follow ESLint recommended rules
- Use explicit types (no `any` unless necessary)
- JSDoc comments for exports

### Documentation

- Use clear, concise language
- Include code examples
- Markdown files should wrap at 100 characters
- Use relative links for cross-references

## Questions?

If you have questions that aren't covered here:

1. Check [existing issues](https://github.com/mesh-sync/standard-meshpack/issues)
2. Open a new issue with the `question` label
3. Reach out to maintainers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to MeshPack! 🚀

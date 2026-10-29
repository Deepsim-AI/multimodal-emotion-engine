# TASK_HUB_I18N_032: Add Bilingual Support to Deepsim Hub

**Priority:** High  
**Type:** Product enhancement  
**Target:** Deepsim Hub and its customer-facing documentation  
**Languages:** English (`en`) and Simplified Chinese (`zh-CN`)  
**Initial product:** Multimodal Emotion Engine (MEE)

## 1. Objective

Extend the existing Deepsim Hub to support English and Simplified Chinese, making the platform accessible to both international and Chinese customers.

The English Hub is already implemented. This task is an incremental enhancement, not a redesign.

The implementation must provide:

1. A visible language selector in the main navigation.
2. Automatic initial language selection based on browser language preferences.
3. Persistent user-selected language preferences.
4. Chinese translations of the customer-facing Hub interface.
5. Chinese versions of MEE product information and user documentation.
6. A reusable internationalization architecture for future Hub products.

Use the language-switching experience of established software platforms such as Ollama as a reference.

## 2. Language Selector

Add a clearly visible language selector to the existing Hub navigation.

In the English interface, display:

`English | 中文`

In the Chinese interface, display:

`中文 | English`

The active language should be visually distinguishable.

Requirements:
- Switching languages must be straightforward.
- The selector must work on desktop and mobile.
- Use text labels rather than relying on national flags.
- Maintain the existing Hub visual design.
- Avoid duplicating navigation elements or introducing unnecessary interface complexity.

When a Chinese user selects English, the interface must return to English. Selecting Chinese must work equally well from the English interface.

## 3. Automatic Language Detection

Implement automatic initial language selection using the browser's language preferences, such as `navigator.languages` and `navigator.language`.

Use the following rules:

1. If the user has explicitly selected a language, respect that selection.
2. If a language preference has previously been saved, reuse it.
3. Otherwise, inspect the browser's preferred languages.
4. Select Simplified Chinese when a supported Chinese language preference is detected.
5. Default to English for unsupported languages or when language detection is unavailable.

At minimum, recognize appropriate Simplified Chinese preferences such as `zh-CN` and `zh-SG`. Handle regional language tags consistently.

An explicit user selection must take precedence over automatic detection.

Persist the preference using an appropriate mechanism, such as `localStorage`, if compatible with the existing architecture.

Do not repeatedly override the user's choice when browser language preferences are checked.

Do not infer the user's actual location from their browser language.

## 4. Language Switching and URL Strategy

Inspect the existing Hub routing before selecting the implementation.

Prefer stable, shareable language-specific URLs where practical.

For example:

- English MEE page: `/en/Deepsim/multimodal-emotion-engine`
- Chinese MEE page: `/zh-cn/Deepsim/multimodal-emotion-engine`
- English documentation: `/en/Deepsim/multimodal-emotion-engine/docs`
- Chinese documentation: `/zh-cn/Deepsim/multimodal-emotion-engine/docs`

These are proposed routes, not mandatory routes if the existing architecture suggests a safer alternative.

Requirements:

- Preserve existing English URLs and backward compatibility.
- Do not break existing bookmarks, package downloads, releases, or registry endpoints.
- Preserve the current page when switching languages if its translation exists.
- Provide a graceful fallback when the corresponding translation is unavailable.
- Avoid redirect loops or conflicts with existing reverse-proxy rules.
- Ensure direct navigation and browser refresh work correctly.

If language-prefixed routes require significant or risky changes, propose a compatible alternative before implementation.

## 5. Translation Scope

Translate the complete customer-facing interface, including:

- Homepage content.
- Main navigation.
- Product cards and descriptions.
- Product feature descriptions.
- Buttons and calls to action.
- Search interface and empty states.
- Documentation navigation.
- User-facing notifications and error messages.
- Other visible interface labels.

Preserve technical identifiers where appropriate, including:

- Product and repository names.
- Package names and distribution identifiers.
- API names and parameter names.
- Commands, code examples, and configuration keys.
- File paths and technical identifiers.

Do not translate technical identifiers in ways that make commands, APIs, or configuration examples incorrect.

## 6. MEE Documentation Localization

The English customer-facing MEE documentation has already been completed.

Use it as the source of truth for creating the Simplified Chinese documentation.

Translate and adapt the existing content into natural, technically accurate Simplified Chinese.

Prioritize:

1. 产品介绍 — Introduction
2. 快速入门 — Getting Started
3. 安装指南 — Installation
4. 配置指南 — Configuration
5. 用户指南 — User Guide
6. 故障排除 — Troubleshooting
7. 常见问题 — FAQ
8. 参考手册 — Reference

Translate additional integration and deployment guides where those capabilities are supported and documented in English.

Requirements:

- Preserve the English documentation's technical accuracy.
- Maintain equivalent navigation and page organization across languages where practical.
- Keep code examples, commands, API identifiers, and configuration keys valid.
- Verify technical instructions against the actual implementation.
- Do not invent unsupported features or APIs.
- Clearly indicate when a page is not yet available in Chinese.
- Avoid publishing empty or misleading translated pages.

Do not rewrite the English documentation unnecessarily as part of this task.

## 7. Reusable Internationalization Architecture

Design the solution so future Deepsim Hub products can support multiple languages without rebuilding the internationalization system.

Separate interface translations from product content.

For example:

`i18n/en.json`

`i18n/zh-CN.json`

These filenames are illustrative. Follow the conventions of the existing technology stack.

The shared architecture should support:

- Centralized interface translations.
- Product-specific localized descriptions.
- Language-aware documentation navigation.
- Persistent language preferences.
- A consistent language selector.
- Additional languages in the future.
- Validation for missing translation keys.

Avoid scattering hardcoded language conditions throughout the application.

Prefer a reusable translation mechanism and consistent language metadata.

Do not introduce a database or complex translation-management platform solely to support two languages.

## 8. Search and Documentation Navigation

Verify that documentation search works in both languages.

Requirements:

- English searches must continue to work.
- Chinese documentation must be discoverable through search.
- Sidebar navigation must display the correct language.
- Breadcrumbs and previous/next links must remain language-aware.
- Switching languages should preserve the current documentation topic when a translation exists.
- Missing translations must be handled gracefully.

If the current search implementation has limitations with Chinese tokenization or indexing, document them and propose an appropriate solution.

## 9. Implementation Phases

### Phase 0 — Audit and Plan

Inspect the completed English Hub and documentation implementation.

Identify:
- Frontend technology and application structure.
- Current routing and URL conventions.
- Documentation rendering architecture.
- Translation-related capabilities already present.
- Reverse-proxy constraints.
- Existing tests and deployment procedures.

Produce a concise implementation plan identifying the required changes, risks, and testing strategy.

Do not redesign the Hub or modify unrelated services.

### Phase 1 — Bilingual Interface

- Add the language selector.
- Implement automatic language detection.
- Persist manual language preferences.
- Translate the main navigation and homepage.
- Translate product cards and customer-facing interface elements.
- Preserve existing English routes and functionality.

### Phase 2 — MEE and Documentation Localization

- Translate the MEE product information.
- Publish the Chinese customer-facing documentation.
- Implement language-aware documentation navigation.
- Verify search, links, and language switching.
- Clearly identify unavailable translations.

### Phase 3 — Reusable Platform Support

- Standardize translation files and language metadata.
- Define conventions for future products.
- Add automated checks for missing translation keys and broken links.
- Document how new products add translations and localized documentation.
- Prepare the architecture for future languages without implementing unnecessary features now.

## 10. Acceptance Criteria

The task is complete when:

1. A visible language selector is available in the Hub navigation.
2. Users can switch between English and Simplified Chinese.
3. Browser language preferences determine the initial language when no saved preference exists.
4. Manual language selection persists across visits.
5. English remains the fallback for unsupported languages.
6. The homepage and customer-facing navigation are available in both languages.
7. MEE product information is available in both languages.
8. The completed English MEE user documentation has a corresponding Chinese version for the initially supported topics.
9. Documentation navigation and search work in both languages.
10. Language switching preserves the current page where a translation exists.
11. Missing translations are handled clearly and safely.
12. Existing product routes, releases, package downloads, and registry functionality continue to work.
13. Desktop and mobile interfaces render correctly.
14. Automated tests cover language detection, persistence, switching, translation completeness, and route behavior.
15. Future products can adopt the shared internationalization architecture without implementing a separate language system.

## 11. Out of Scope

Do not include the following unless separately approved:

- A complete Hub redesign.
- Traditional Chinese or additional languages.
- An external translation service.
- Automatic machine translation at runtime.
- A complex translation-management CMS.
- Unrelated package-registry or infrastructure changes.
- Changes to product APIs or software functionality.

## 12. Required Reporting

Before implementation, report the existing architecture and the proposed approach.

After implementation, provide:

- Files changed.
- Translation coverage.
- Routes affected.
- Tests executed and results.
- Evidence that existing English functionality remains intact.
- Known limitations.
- Deployment and rollback details.
- Recommendations for integrating future Hub products.

Distinguish verified results from assumptions.

## Final Direction

Implement English and Simplified Chinese as the first two languages of Deepsim Hub.

Prioritize a seamless user experience: automatic language selection, a visible manual switch, persistent preferences, language-aware URLs where practical, and accurate Chinese product documentation.

Build this as a shared platform capability so that future Deepsim products can adopt it consistently.

**Start by auditing the existing implementation, then proceed incrementally. Preserve the completed English Hub and avoid unnecessary production or infrastructure changes.**
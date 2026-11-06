# User interfaces

**Conditional (UI):** this whole page applies when the project has a user
interface. Bluebird's `frontend/src/styles.ts`, `docs/STYLES.md` and the
linter checks in `frontend/tools/eslint/` are the working example.

## Design system

1. **Use an existing framework**, such as Material, where possible. For a new
   project, prototype the app in more than one design framework and let the
   maintainer pick. Whatever the framework, every visual decision composes
   one roles module, and the framework's raw utilities don't appear at call
   sites. Bluebird: Tailwind under `styles.ts`.
2. **Build every element from shared parts.** A new button or menu is not
   hand-crafted: it uses the shared component or style role other buttons and
   menus use, so they all look and behave the same. A unique look or
   behaviour needs a demonstrated reason.
3. **Couple behaviours that belong together**, from the start. In Bluebird,
   clicking a marker showed its popup while hovering a fire showed one
   automatically. Those two should have shared one code path, and records
   0125 and 0161 later made them one.
4. **Every change fits the rest of the UI.** Button sizes rarely change, and
   fonts almost never. A change that breaks from the existing styles needs
   the maintainer's approval.
5. **Tests and the linter enforce the design.** A shared styles module in
   source code defines every type, color, radius and surface. Tests fail a
   wrong font, a one-off button, or a color that misses its contrast ratio.
   Lint rules fail a value spelled outside the module that owns it.
6. **Every colour value has one owner**, in every channel it reaches. No
   component names a hue. Map paint, canvas drawing, generated popup HTML
   and chart props each get an owning module too, because CSS never reaches
   them and that's where drift hides. The linter fails a colour literal
   anywhere else. Bluebird: records 0009 and 0112.
7. **The type ramp has a floor, and shadows have a scale**, both enforced:
   a smallest size for text a reader reads, a larger one for anything
   pressed, and a few elevation steps. Bluebird: record 0131 (11px, 12px,
   three shadows).
8. **Themes are tokens.** Every colour role paints a semantic token with a
   value per theme, never a palette step. A new token needs a value and a
   contrast measurement in each theme, and a colour that misses its ratio
   fails a test. Which themes, and which is the default, is an interview
   choice. Bluebird: record 0158.
9. **Responsive and live.** Everything works at desktop and phone widths.
   An element updates the moment the data it shows changes, even while it is
   open: an open context menu showing data that another control edits
   updates in place.
10. **Simple, fast, efficient and beautiful**, in that order of attention,
    and always in the project's own style.

## Behaviour

11. **A costly action is an explicit commit.** An action that spends
    upstream quota or real work waits for an explicit button. A change that
    only re-presents data already held applies live. A run that fails or is
    cancelled leaves the previous state exactly as it was. Bluebird: records
    0003 and 0093.
12. **A disabled control says every reason it's disabled**, never only the
    first, so a button never goes dead without a word. Status messages live
    in one place, not beside each control. Bluebird: records 0062, 0210 and
    0028.
13. **Accessibility is measured, beyond axe.** WCAG AA, pinned in tests:
    4.5:1 for text, 3:1 for UI. A control's accessible name is the words it
    shows. Focus moves to whatever replaced the focused element. One live
    region announces messages. axe runs in every theme. Bluebird: records
    0089 and 0090.
14. **Conditional (shareable state):** URL parameters are readable by a
    person, the parser is tolerant so old links keep opening, and a link
    restores what it can and says what it couldn't. A link carries the
    subject, never the viewer's preferences, which stay in local storage.
    Bluebird: record 0237.
15. **Conditional (single-page app):** a tab left open across a release
    reloads once, silently, when it asks for a chunk the new build doesn't
    have, and client-side caches carry the build that wrote them. Bluebird:
    records 0087 and 0095.

## Copy

16. **Every user-facing string is approved** by the maintainer before it
    ships, and no tooltip is added without asking, because a tooltip doesn't
    exist on touch.
17. **The copy rules.** Sentence case everywhere, buttons included. An error
    says what's wrong, and gives a remedy only where the remedy works; "Try
    again later." ends a transient error. Never show an exception type or an
    HTTP status. Each message fits one line at the narrowest supported
    width. No em dashes. No on-screen prose explaining a control; fix the
    control instead. Name things in the words the UI already shows, and
    don't coin labels. Bluebird: `docs/STYLES.md`, Copy rules.

## Mockups

18. **Mockups first.** ASCII for a small change, an Artifact for a large one,
    and screenshots in every theme before review. Mockups run on fake,
    fuzzed data, never real quota. A design choice with knobs gets an
    interactive lab, not a gallery of screenshots, and every lab has an
    Export JSON button so the maintainer can paste the chosen settings back.

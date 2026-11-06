# User interfaces

**Conditional (UI):** this whole page applies when the project has a user
interface.

## Design system

1. **Use an existing framework**, such as Material, where possible. For a new
   project, prototype the app in more than one design framework and let the
   maintainer pick. Whatever the framework, every visual decision composes one
   roles module, and the framework's raw utilities don't appear at call sites.
2. **Build every element from shared parts.** A new button or menu is not
   hand-crafted: it uses the shared component or style role other buttons and
   menus use, so they all look and behave the same. A unique look or
   behaviour needs a demonstrated reason.
3. **Couple behaviours that belong together**, from the start. If clicking
   one kind of item opens its details and hovering another opens the same
   kind of details, both go through one code path.
4. **Every change fits the rest of the UI.** Button sizes rarely change, and
   fonts almost never. A change that breaks from the existing styles needs
   the maintainer's approval.
5. **Tests and the linter enforce the design.** A shared styles module in
   source code defines every type, color, radius and surface. Tests fail a
   wrong font, a one-off button, or a color that misses its contrast ratio.
   Lint rules fail a value spelled outside the module that owns it.
6. **Every colour value has one owner**, in every channel it reaches. No
   component names a hue. Channels CSS never reaches, such as canvas drawing
   and chart options, get an owning module too, because that's where drift
   hides. The linter fails a colour literal anywhere else.
7. **The type ramp has a floor, and shadows have a scale**, both enforced: a
   smallest size for text a reader reads, a larger one for anything pressed,
   and a few elevation steps.
8. **Themes are tokens.** Every colour role paints a semantic token with a
   value per theme, never a palette step. A new token needs a value and a
   contrast measurement in each theme, and a colour that misses its ratio
   fails a test. Which themes, and which is the default, is an interview
   choice.
9. **Responsive and live.** Everything works at desktop and phone widths.
   An element updates the moment the data it shows changes, even while it is
   open: an open context menu showing data that another control edits
   updates in place.
10. **Simple, fast, efficient and beautiful**, in that order of attention,
    and always in the project's own style.

## Behaviour

11. **A disabled control says every reason it's disabled**, never only the
    first, so a button never goes dead without a word. Status messages live in
    one place, not beside each control.
12. **Accessibility is measured, beyond axe.** WCAG AA, pinned in tests: 4.5:1
    for text, 3:1 for UI. A control's accessible name is the words it shows.
    Focus moves to whatever replaced the focused element. One live region
    announces messages. axe runs in every theme.
13. **Conditional (shareable state):** URL parameters are readable by a
    person, the parser is tolerant so old links keep opening, and a link
    restores what it can and says what it couldn't. A link carries the
    subject, never the viewer's preferences, which stay in local storage.
14. **Conditional (single-page app):** a tab left open across a release
    reloads once, silently, when it asks for a chunk the new build doesn't
    have, and client-side caches carry the build that wrote them.

15. **An action that fails or is cancelled changes nothing.** The screen
    returns to exactly the state before it, and partial results are discarded.

## Copy

16. **Every user-facing string is approved** by the maintainer before it
    ships, and no tooltip is added without asking, because a tooltip doesn't
    exist on touch.
17. **The copy rules.** Sentence case everywhere, buttons included. An error
    says what's wrong, and gives a remedy only where the remedy works; "Try
    again later." ends a transient error. Never show an exception type or an
    HTTP status. Each message fits one line at the narrowest supported width.
    No on-screen prose explaining a control; fix the control instead. Name
    things in the words the UI already shows. The global writing rules apply
    too.

## Mockups

18. **Mockups first.** ASCII for a small change, an Artifact for a large one,
    and screenshots in every theme before review. Mockups run on fake,
    fuzzed data. A design choice with knobs gets an
    interactive lab, not a gallery of screenshots, and every lab has an
    Export JSON button so the maintainer can paste the chosen settings back.

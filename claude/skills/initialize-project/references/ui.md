# User interfaces

**Conditional (UI):** this whole page applies when the project has a user
interface. Bluebird's `frontend/src/styles.ts`, `docs/STYLES.md` and the
linter checks in `frontend/tools/eslint/` are the working example.

1. **Use an existing framework**, such as Material, where possible. For a new
   project, prototype the app in more than one design framework and let the
   maintainer pick.
2. **Build every element from shared parts.** A new button or menu is not
   hand-crafted: it uses the shared component or style role other buttons and
   menus use, so they all look and behave the same. A unique look or
   behaviour needs a demonstrated reason.
3. **Couple behaviours that belong together**, from the start. In Bluebird,
   clicking a marker showed its popup while hovering a fire showed one
   automatically. Those two should have shared one code path.
4. **Every change fits the rest of the UI.** Button sizes rarely change, and
   fonts almost never. A change that breaks from the existing styles needs
   the maintainer's approval.
5. **Tests and the linter enforce the design.** A shared styles module in
   source code defines every type, color, radius and surface. Tests fail a
   wrong font, a one-off button, or a color that misses its contrast ratio.
   Lint rules fail a value spelled outside the module that owns it.
6. **Responsive and live.** Everything works at desktop and phone widths.
   An element updates the moment the data it shows changes, even while it is
   open: an open context menu showing data that another control edits
   updates in place.
7. **Simple, fast, efficient and beautiful**, in that order of attention, and
   always in the project's own style.
8. **Copy.** Every user-facing string is approved by the maintainer before it
   ships, and no tooltip is added without asking, because a tooltip doesn't
   exist on touch.
9. **Mockups first.** ASCII for a small change, an Artifact for a large one,
   and screenshots in every theme before review.

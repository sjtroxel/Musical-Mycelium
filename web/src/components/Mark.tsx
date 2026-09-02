import { geometry } from "./mark";

/*
 * The masthead mark. Same drawing as `public/favicon.svg` and deliberately the same STRING - the
 * geometry is written once in `mark.ts` and injected here, so the logo and the favicon cannot drift
 * into two slightly different pictures. The markup is a module constant built from numbers in this
 * repo; nothing external reaches it.
 *
 * No ground rect: the masthead already sits on `--ground`. The favicon carries one because a browser
 * tab strip is not ours to control.
 *
 * `aria-hidden` because the <h1> beside it already says "Musical Mycelium", and a screen reader
 * announcing the name twice is worse than not announcing the mark at all.
 */
export function Mark({ size = 34 }: { readonly size?: number }) {
  return (
    <svg
      className="mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      dangerouslySetInnerHTML={{ __html: geometry() }}
    />
  );
}

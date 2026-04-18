/**
 * Shared markdown rendering config.
 * Opens all links in new tabs to prevent navigating away from the app.
 */
export const markdownComponents = {
  a: ({ href, children, ...props }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
      {children}
    </a>
  ),
};

import { Card, createTheme, Paper, type MantineColorsTuple } from '@mantine/core';

// Built around the original app's accent, #1a56db (index 6).
const accent: MantineColorsTuple = [
  '#ebf1ff',
  '#d4e0fd',
  '#a6bef6',
  '#7499f0',
  '#4b7aeb',
  '#3266e8',
  '#1a56db',
  '#1547c2',
  '#0f3dad',
  '#063399',
];

export const theme = createTheme({
  primaryColor: 'accent',
  colors: { accent },
  fontFamily: "'Inter Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
  fontFamilyMonospace: "'JetBrains Mono Variable', ui-monospace, SFMono-Regular, Menlo, monospace",
  headings: {
    fontFamily: "'Inter Variable', system-ui, sans-serif",
    fontWeight: '650',
  },
  defaultRadius: 'md',
  components: {
    Card: Card.extend({ defaultProps: { withBorder: true, radius: 'md', padding: 'lg' } }),
    Paper: Paper.extend({ defaultProps: { radius: 'md' } }),
  },
});

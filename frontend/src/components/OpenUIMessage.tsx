import { Renderer } from '@openuidev/react-lang';
import { openuiChatLibrary, ThemeProvider } from '@openuidev/react-ui';

export default function OpenUIMessage({ response, mode }: { response: string; mode: 'light' | 'dark' }) {
  return <ThemeProvider mode={mode}><Renderer response={response} library={openuiChatLibrary} /></ThemeProvider>;
}

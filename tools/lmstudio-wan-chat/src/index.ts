import { type PluginContext, rawFunctionTool } from '@lmstudio/sdk';
import { preprocess } from './promptPreprocessor.mjs';
import { toolsProvider } from './toolsProxy.mjs';

export async function main(context: PluginContext) {
  context.withPromptPreprocessor(preprocess);
  context.withToolsProvider(ctl => toolsProvider(ctl, rawFunctionTool));
}

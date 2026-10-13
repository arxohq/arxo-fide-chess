import type { CaseInput } from '@arxo/law';
export type CaseName = "TouchIntentUnknown" | "FirstIllegal" | "SecondIllegal" | "SecondIllegalNoMate" | "FlagFall" | "FlagFallNoMate" | "RapidFirstIllegal" | "BlitzFirstIllegalCompetitive" | "ShortOfTimeRecording" | "DeviceWarning";
export declare const caseNames: readonly CaseName[];
export declare const game: 'urn:example:chess:game';
export declare const white: 'urn:example:chess:white';
export declare const black: 'urn:example:chess:black';
export declare const king: 'urn:example:chess:king';
export declare function getCaseInput(name: CaseName): CaseInput;

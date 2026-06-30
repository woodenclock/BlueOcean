/* eslint-disable @typescript-eslint/no-explicit-any */

// Referenced from https://stackoverflow.com/a/65642944
export type SnakeToCamelCase<S extends string> =
  S extends `${infer T}_${infer U}`
    ? `${T}${Capitalize<SnakeToCamelCase<U>>}`
    : S;

export type CamelToSnakeCase<S extends string> =
  S extends `${infer T}${infer U}`
    ? `${T extends Capitalize<T> ? '_' : ''}${Lowercase<T>}${CamelToSnakeCase<U>}`
    : S;

export type SnakeToCamelCaseNested<T> = T extends object
  ? {
      [K in keyof T as SnakeToCamelCase<K & string>]: SnakeToCamelCaseNested<
        T[K]
      >;
    }
  : T;

export type CamelToSnakeCaseNested<T> = T extends object
  ? {
      [K in keyof T as CamelToSnakeCase<K & string>]: CamelToSnakeCaseNested<
        T[K]
      >;
    }
  : T;

export function camelToSnake(input: string): string {
  return input.replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase();
}

export function snakeToCamel(input: string): string {
  return input.replace(/_(\w)/g, (_, letter) => letter.toUpperCase());
}

export function snakeToCamelCaseCast<CamelT>(
  input: CamelToSnakeCaseNested<CamelT>,
): CamelT {
  const output: Record<string, any> = {};
  for (const [key, value] of Object.entries(input as Record<string, any>)) {
    output[snakeToCamel(key)] = value;
  }
  return output as CamelT;
}

export function camelToSnakeCaseCast<SnakeT>(
  input: SnakeToCamelCaseNested<SnakeT>,
): SnakeT {
  const output: Record<string, any> = {};
  for (const [key, value] of Object.entries(input as Record<string, any>)) {
    output[camelToSnake(key)] = value;
  }
  return output as SnakeT;
}

type IconName = "spark" | "note" | "clock" | "shield" | "code" | "heart";

const paths: Record<IconName, React.ReactNode> = {
  spark: <path d="M12 2l1.5 5.2L19 9l-5.5 1.8L12 16l-1.5-5.2L5 9l5.5-1.8L12 2Zm6 12 .8 2.7L22 18l-3.2 1.3L18 22l-.8-2.7L14 18l3.2-1.3L18 14Z" />,
  note: <path d="M6 3h9l3 3v15H6V3Zm8 1v4h4M9 12h6M9 16h6" />,
  clock: <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v5l3 2" />,
  shield: <path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6l-7-3Zm-3 9 2 2 4-5" />,
  code: <path d="m8 8-4 4 4 4m8-8 4 4-4 4m-3-10-2 12" />,
  heart: <path d="M12 20 4.8 13C1 9.3 6.5 3.5 10.8 7.8L12 9l1.2-1.2C17.5 3.5 23 9.3 19.2 13L12 20Z" />,
};

export function Icon({ name }: Readonly<{ name: IconName }>) {
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

import { Component, type ErrorInfo, type ReactNode } from "react";
import s from "./ErrorBoundary.module.css";

/**
 * Un evento mal formado del motor no puede llevarse puesta la consola.
 *
 * Sin esto, un `plan` con una forma inesperada deja la pantalla en blanco y el único
 * rastro queda en la consola del navegador — que es justo donde no vas a mirar cuando
 * estás probando el motor.
 */
export default class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[mapo-ui]", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className={s.wrap} role="alert">
        <h1>La consola se rompió, no el motor.</h1>
        <p>
          Algo en la interfaz falló al renderizar. Lo más probable es un evento con una
          forma que <code>src/types.ts</code> no espera.
        </p>
        <pre className={s.msg}>{this.state.error.message}</pre>
        <button type="button" onClick={() => this.setState({ error: null })}>
          Reintentar el render
        </button>
        <p className={s.foot}>
          Si vuelve a pasar, mirá la consola del navegador: ahí queda el stack del
          componente.
        </p>
      </div>
    );
  }
}

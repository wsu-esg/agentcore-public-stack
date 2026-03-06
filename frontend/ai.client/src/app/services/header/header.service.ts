import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class HeaderService {
  private _showContent = signal(true);
  readonly showContent = this._showContent.asReadonly();

  showHeaderContent() {
    this._showContent.set(true);
  }

  hideHeaderContent() {
    this._showContent.set(false);
  }
}

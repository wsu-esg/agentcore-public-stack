import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { SessionService } from '../../session/services/session/session.service';
import { SidenavService } from '../../services/sidenav/sidenav.service';

@Component({
  selector: 'app-topnav',
  imports: [],
  templateUrl: './topnav.html',
  styleUrl: './topnav.css',
})
export class Topnav {
  private router = inject(Router);
  protected sidenavService = inject(SidenavService);
  protected sessionService = inject(SessionService);
  readonly currentSession = this.sessionService.currentSession;

  newChat() {
    this.router.navigate(['']);
  }

  openSidenav() {
    this.sidenavService.open();
  }
}

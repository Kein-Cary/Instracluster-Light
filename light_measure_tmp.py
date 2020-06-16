import numpy as np
import astropy.constants as C
import astropy.units as U
from astropy import cosmology as apcy
from numba import vectorize
# constant
vc = C.c.to(U.km/U.s).value
G = C.G.value # gravitation constant
Ms = C.M_sun.value # solar mass
kpc2m = U.kpc.to(U.m)
Msun2kg = U.M_sun.to(U.kg)

kpc2cm = U.kpc.to(U.cm)
Mpc2pc = U.Mpc.to(U.pc)
Mpc2cm = U.Mpc.to(U.cm)
Lsun2erg_s = U.L_sun.to(U.erg/U.s)
rad2arcsec = U.rad.to(U.arcsec)
pc2cm = U.pc.to(U.cm)
Lsun = C.L_sun.value*10**7

# cosmology model
Test_model = apcy.Planck15.clone(H0 = 67.74, Om0 = 0.311)
H0 = Test_model.H0.value
h = H0/100
Omega_m = Test_model.Om0
Omega_lambda = 1.-Omega_m
Omega_k = 1.- (Omega_lambda + Omega_m)
DH = vc/H0

def flux_recal(data, z0, zref):
	obs = data
	z0 = z0
	z1 = zref
	Da0 = Test_model.angular_diameter_distance(z0).value
	Da1 = Test_model.angular_diameter_distance(z1).value
	flux = obs * (1 + z0)**4 * Da0**2 / ((1 + z1)**4 * Da1**2)
	return flux

def light_measure_pn(data, Nbin, R_small, R_max, cx, cy, psize, z0, pn):

	Da0 = Test_model.angular_diameter_distance(z0).value
	Nx = data.shape[1]
	Ny = data.shape[0]
	x0 = np.linspace(0, Nx-1, Nx)
	y0 = np.linspace(0, Ny-1, Ny)

	pix_id = np.array(np.meshgrid(x0,y0))
	theta = np.arctan2((pix_id[1,:]-cy), (pix_id[0,:]-cx))
	chi = theta * 180 / np.pi

	divi_r = np.logspace(np.log10(R_small), np.log10(R_max), Nbin)
	r = (divi_r * 1e-3 * rad2arcsec / Da0) / psize
	ia = r <= 1. # smaller than 1 pixel
	ib = r[ia]
	ic = len(ib)
	rbin = r[ic:]
	set_r = divi_r[ic:]

	intens = np.zeros(len(r) - ic, dtype = np.float)
	intens_r = np.zeros(len(r) - ic, dtype = np.float)
	intens_err = np.zeros(len(r) - ic, dtype = np.float)
	N_pix = np.zeros(len(r) - ic, dtype = np.float)

	dr = np.sqrt(((2*pix_id[0] + 1) / 2 - (2*cx + 1) / 2)**2 + 
		((2*pix_id[1] + 1) / 2 - (2*cy + 1) / 2)**2)

	for k in range(len(rbin) - 1):
		cdr = rbin[k + 1] - rbin[k]
		d_phi = (pn * cdr / ( 0.5 * (rbin[k] + rbin[k + 1]) ) ) * 180 / np.pi
		N_phi = np.int(360 / d_phi) + 1
		phi = np.linspace(0, 360, N_phi)
		phi = phi - 180

		ir = (dr >= rbin[k]) & (dr < rbin[k + 1])
		bool_sum = np.sum(ir)

		r_iner = set_r[k] ## useing radius in unit of kpc
		r_out = set_r[k + 1]

		if bool_sum == 0:
			intens[k] = np.nan
			intens_err[k] = np.nan
			N_pix[k] = np.nan
			intens_r[k] = 0.5 * (r_iner + r_out)
		else:
			samp_f = data[ir]
			samp_chi = chi[ir]

			tot_flux = np.nanmean(samp_f)
			tot_area = psize**2
			intens[k] = tot_flux
			N_pix[k] = len(samp_f)
			intens_r[k] = 0.5 * (r_iner + r_out)

			tmpf = []
			for tt in range(len(phi) - 1):
				iv = (samp_chi >= phi[tt]) & (samp_chi <= phi[tt+1])
				set_samp = samp_f[iv]
				ttf = np.nanmean(set_samp)
				tmpf.append(ttf)

			# rms of flux
			tmpf = np.array(tmpf)
			id_inf = np.isnan(tmpf)
			tmpf[id_inf] = np.nan
			id_zero = tmpf == 0
			tmpf[id_zero] = np.nan
			id_nan = np.isnan(tmpf)
			id_fals = id_nan == False
			Tmpf = tmpf[id_fals]
			intens_err[k] = np.nanstd(tmpf) / np.sqrt(len(Tmpf) - 1)

	intens[intens == 0] = np.nan
	Intns = intens * 1

	intens_r[intens_r == 0] = np.nan
	Intns_r = intens_r * 1
	
	intens_err[intens_err == 0] = np.nan
	Intns_err = intens_err * 1

	N_pix[ N_pix == 0] = np.nan
	Npix = N_pix * 1

	return Intns, Intns_r, Intns_err, Npix

def flux_scale(data, z0, zref, pix_z0):
	obs = data / pix_z0**2
	scaled_sb = obs *( (1 + z0)**4 / (1 + zref)**4 )

	Da0 = Test_model.angular_diameter_distance(z0).value
	Da1 = Test_model.angular_diameter_distance(zref).value
	s0 = pix_z0**2
	s1 = pix_z0**2 * ( Da0**2 / Da1**2 )

	pix_zf = np.sqrt(s1)
	sb_ref = scaled_sb * s1
	return sb_ref, pix_zf

def angu_area(s0, z0, zref):
	s0 = s0
	z0 = z0
	z1 = zref
	Da0 = Test_model.angular_diameter_distance(z0).value
	Da1 = Test_model.angular_diameter_distance(z1).value
	angu_S = s0*Da0**2/Da1**2
	return angu_S

def light_measure_Z0(data, pix_size, r_lim, R_pix, cx, cy, bins):
	"""
	This part use for measuring surface brightness(SB) of objs those redshift 
		is too small or is zero. ie. the sky brightness.
	data : the image use to measure SB profile
	pix_size : pixel size, in unit of "arcsec"
	r_lim : the smallest radius of SB profile
	R_pix : the radius of objs in unit of pixel number
	cx, cy : the central position of objs in the image frame
	"""
	Nx = data.shape[1]
	Ny = data.shape[0]
	x0 = np.linspace(0, Nx-1, Nx)
	y0 = np.linspace(0, Ny-1, Ny)
	pix_id = np.array(np.meshgrid(x0,y0))

	theta = np.arctan2((pix_id[1,:] - cy), (pix_id[0,:] - cx))
	chi = theta * 180 / np.pi
	# radius in unit of pixel number
	rbin = np.logspace(np.log10(r_lim), np.log10(R_pix), bins)

	intens = np.zeros(len(rbin), dtype = np.float)
	intens_err = np.zeros(len(rbin), dtype = np.float)
	Angl_r = np.zeros(len(rbin), dtype = np.float)

	indx = []

	dr = np.sqrt(((2*pix_id[0] + 1) / 2 - (2*cx + 1) / 2)**2 + 
		((2*pix_id[1] + 1) / 2 - (2*cy + 1) / 2)**2)

	for k in range(len(rbin) - 1):
		cdr = rbin[k + 1] - rbin[k]
		d_phi = (cdr / ( 0.5 * (rbin[k] + rbin[k + 1]) ) ) * 180 / np.pi
		N_phi = np.int(360 / d_phi) + 1
		phi = np.linspace(0, 360, N_phi)
		phi = phi - 180

		ir = (dr >= rbin[k]) & (dr < rbin[k + 1])

		indx.append(ir)

		bool_sum = np.sum(ir)

		r_iner = rbin[k]
		r_out = rbin[k + 1]

		if bool_sum == 0:
			intens[k] = np.nan
			intens_err[k] = np.nan
			Angl_r[k] = 0.5 * (r_iner + r_out) * pix_size

		else:
			samp_flux = data[ir]
			samp_chi = chi[ir]
			tot_flux = np.nanmean(samp_flux)
			tot_area = pix_size**2
			intens[k] = tot_flux
			Angl_r[k] = 0.5 * (r_iner + r_out) * pix_size

			tmpf = []
			for tt in range(len(phi) - 1):
				iv = (samp_chi >= phi[tt]) & (samp_chi <= phi[tt+1])
				set_samp = samp_flux[iv]
				ttf = np.nanmean(set_samp)
				tmpf.append(ttf)

			# rms of flux
			tmpf = np.array(tmpf)
			id_inf = np.isnan(tmpf)
			tmpf[id_inf] = np.nan
			id_zero = tmpf == 0
			tmpf[id_zero] = np.nan
			id_nan = np.isnan(tmpf)
			id_fals = id_nan == False
			Tmpf = tmpf[id_fals]
			intens_err[k] = np.nanstd(tmpf) / np.sqrt(len(Tmpf) - 1)

	intens[intens == 0] = np.nan
	Intns = intens * 1

	intens_err[intens_err == 0] = np.nan
	Intns_err = intens_err * 1

	Angl_r[Angl_r == 0] = np.nan

	r_edg = rbin * pix_size

	return Intns, Angl_r, Intns_err, indx, r_edg

def light_measure_rn_Z0(data, R_low, R_up, cx, cy, pix_size, z0):
	"""
	use to get the surface brightness for given radius
	data : data used to measure brightness (2D-array)
	R_low, R_up : the low_limit and up_limit of the given radius (in unit of pix-number)
	cx, cy : the center location / the reference point of the radius
	pix_size : the pixel size in unit of arcsec
	z0 : the redshift of the data 
	"""

	Nx = data.shape[1]
	Ny = data.shape[0]
	x0 = np.linspace(0, Nx-1, Nx)
	y0 = np.linspace(0, Ny-1, Ny)
	pix_id = np.array(np.meshgrid(x0,y0))

	dr = np.sqrt(((2*pix_id[0] + 1) / 2 - (2*cx + 1) / 2)**2 + 
		((2*pix_id[1] + 1) / 2 - (2*cy + 1) / 2)**2)
	idu = (dr >= R_low) & (dr <= R_up)
	Intns = np.nanmean( data[idu] )

	theta = np.arctan2((pix_id[1,:] - cy), (pix_id[0,:] - cx))
	chi = theta * 180 / np.pi
	samp_chi = chi[idu]
	samp_flux = data[idu]

	cdr = R_up - R_low
	d_phi = ( cdr / (0.5 * (R_low + R_up) ) ) * 180 / np.pi
	N_phi = np.int(360 / d_phi) + 1
	phi = np.linspace(0, 360, N_phi)
	phi = phi - 180.

	tmpf = []
	for tt in range(len(phi) - 1):
		idv = (samp_chi >= phi[tt]) & (samp_chi <= phi[tt + 1])
		set_samp = samp_flux[idv]

		ttf = np.nanmean(set_samp)
		tmpf.append(ttf)

	# rms of flux
	tmpf = np.array(tmpf)
	id_inf = np.isnan(tmpf)
	tmpf[id_inf] = np.nan
	id_zero = tmpf == 0
	tmpf[id_zero] = np.nan
	id_nan = np.isnan(tmpf)
	id_fals = id_nan == False
	Tmpf = tmpf[id_fals]
	Intns_err = np.nanstd(tmpf) / np.sqrt(len(Tmpf) - 1)

	Intns_r = (0.5 * (R_low + R_up) ) * pix_size

	return Intns_r, Intns, Intns_err, idu
